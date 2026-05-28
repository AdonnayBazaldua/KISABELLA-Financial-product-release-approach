"""Agente Orquestador — sintesis ejecutiva con LLM (Sprint 3).

Score y veredicto son SIEMPRE deterministicos (weighted_final_score + verdict_from_score).
El LLM solo genera la justificacion rica cuando >=3 agentes OK.
Fallback: si el LLM falla, se usa la justificacion mecanica.
"""

from __future__ import annotations

from agents.base import load_prompt
from agents.calculations.scoring import (
    count_ok,
    degraded_verdict,
    verdict_from_score,
    weighted_final_score,
)
from agents.contracts import (
    AgentError,
    AgentResult,
    FinalVerdict,
    OrchestratorSynthesis,
    PipelineState,
    SpecialistName,
)
from agents.llm_client import LLMClient

_PROMPT = load_prompt("orchestrator")


def _short_summary(name: str, item: AgentResult | AgentError) -> str:
    if isinstance(item, AgentResult):
        return f"[{name} — score {item.score}] {item.veredicto_corto}"
    return f"[{name} — fallo: {item.error_type}] {item.error_message[:120]}"


def _build_mechanical_justification(
    results: dict[SpecialistName, AgentResult | AgentError],
    score: int,
    verdict: str,
) -> str:
    lines = [
        f"Veredicto integrado: {verdict} (score compuesto {score}/100).",
        f"Agentes evaluados: {count_ok(results)} de {len(results)} OK.",
        "",
        "Resumen por agente:",
    ]
    for name in ("financiero", "mercado", "riesgo", "estrategia"):
        if name in results:
            lines.append(f"- {_short_summary(name, results[name])}")
        else:
            lines.append(f"- [{name}] no ejecutado")
    text = "\n".join(lines)
    if len(text) < 100:
        text = text + " " * (100 - len(text))
    return text


def _build_agent_analyses_block(
    results: dict[SpecialistName, AgentResult | AgentError],
) -> str:
    blocks = []
    for name in ("financiero", "mercado", "riesgo", "estrategia"):
        item = results.get(name)
        if isinstance(item, AgentResult):
            blocks.append(
                f"--- AGENTE {name.upper()} (score {item.score}/100) ---\n"
                f"Veredicto: {item.veredicto_corto}\n"
                f"Analisis:\n{item.analisis_extenso}\n"
                f"Hallazgos: {', '.join(item.hallazgos_clave)}\n"
                f"Recomendaciones: {', '.join(item.recomendaciones)}"
            )
        elif isinstance(item, AgentError):
            blocks.append(
                f"--- AGENTE {name.upper()} (FALLO: {item.error_type}) ---\n"
                f"{item.error_message[:200]}"
            )
        else:
            blocks.append(f"--- AGENTE {name.upper()} (NO EJECUTADO) ---")
    return "\n\n".join(blocks)


async def _llm_justification(
    results: dict[SpecialistName, AgentResult | AgentError],
    score: int,
    verdict: str,
    ok_count: int,
    llm: LLMClient,
) -> str | None:
    try:
        analyses = _build_agent_analyses_block(results)
        user_msg = _PROMPT.user_template.format(
            verdict=verdict,
            score=score,
            ok_count=ok_count,
            total_count=len(results),
            agent_analyses=analyses,
        )
        synthesis = await llm.request_structured(
            system=_PROMPT.system,
            user=user_msg,
            schema=OrchestratorSynthesis,
        )
        return synthesis.justificacion
    except Exception:
        return None


async def synthesize_verdict(
    state: PipelineState, llm: LLMClient
) -> FinalVerdict:
    results = state.get("agent_results", {})
    score = weighted_final_score(results)
    ok = count_ok(results)

    if ok <= 2:
        verdict, rhr, confidence = degraded_verdict(results, score)
        justification = _build_mechanical_justification(results, score, verdict)
    else:
        verdict = verdict_from_score(score)
        rhr = False
        confidence = "high" if ok == 4 else "medium"

        llm_just = await _llm_justification(results, score, verdict, ok, llm)
        justification = (
            llm_just
            if llm_just and len(llm_just) >= 100
            else _build_mechanical_justification(results, score, verdict)
        )

    return FinalVerdict(
        veredicto=verdict,
        score_final=score,
        justificacion=justification,
        requires_human_review=rhr,
        confidence=confidence,
        warn_flags=state.get("warn_flags", []),
    )


def build_orchestrator_node(llm: LLMClient):
    async def _node(state: PipelineState) -> dict:
        return {"final_verdict": await synthesize_verdict(state, llm)}

    _node.__name__ = "orchestrator_node"
    return _node
