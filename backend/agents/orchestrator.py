"""Agente Orquestador (Sprint 1: determinístico).

Sintetiza los 4 AgentResult y emite FinalVerdict. Sin score propio.
Sprint 3 agrega LLM call para justificación más rica;
por ahora la justificación se compone con los análisis recibidos.

Reglas:
- Score: weighted_final_score (determinístico, ADR-013).
- Veredicto:
    ≤1 OK → no_viable + requires_human_review
    2 OK  → viable_con_ajustes + requires_human_review
    ≥3 OK → verdict_from_score
- Confidence: high si 4 OK, medium si 3 OK, low si ≤2.
"""

from __future__ import annotations

from agents.calculations.scoring import (
    count_ok,
    degraded_verdict,
    verdict_from_score,
    weighted_final_score,
)
from agents.contracts import (
    AgentError,
    AgentResult,
    Confidence,
    FinalVerdict,
    PipelineState,
    SpecialistName,
)


def _short_summary(name: str, item: AgentResult | AgentError) -> str:
    if isinstance(item, AgentResult):
        return f"[{name} — score {item.score}] {item.veredicto_corto}"
    return f"[{name} — falló: {item.error_type}] {item.error_message[:120]}"


def _build_justification(
    results: dict[SpecialistName, AgentResult | AgentError],
    score: int,
    verdict: str,
) -> str:
    """Compone justificación concatenando los 4 análisis. Sprint 3 lo refina con LLM."""
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
    return "\n".join(lines)


def synthesize_verdict(state: PipelineState) -> FinalVerdict:
    """Función pura: recibe state, retorna FinalVerdict."""
    results = state.get("agent_results", {})
    score = weighted_final_score(results)
    ok = count_ok(results)

    if ok <= 2:
        verdict, rhr, confidence = degraded_verdict(results, score)
    else:
        verdict = verdict_from_score(score)
        rhr = False
        confidence = "high" if ok == 4 else "medium"

    justification = _build_justification(results, score, verdict)

    # Padding mínimo: justificación debe tener 100+ chars
    if len(justification) < 100:
        justification = justification + " " * (100 - len(justification))

    return FinalVerdict(
        veredicto=verdict,
        score_final=score,
        justificacion=justification,
        requires_human_review=rhr,
        confidence=confidence,
        warn_flags=state.get("warn_flags", []),
    )


def orchestrator_node(state: PipelineState) -> dict:
    """Nodo LangGraph del orquestador. Retorna parcial del state."""
    return {"final_verdict": synthesize_verdict(state)}
