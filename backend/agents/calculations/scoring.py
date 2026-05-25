"""Scoring compuesto + lógica de degradación graceful.

Pesos por agente (ADR-013):
- Financiero: 0.35 (único con cálculo determinístico auditable)
- Mercado:    0.25
- Riesgo:     0.20
- Estrategia: 0.20

Degradación graceful (CLAUDE.md):
- ≥3 agentes OK → veredicto normal del orquestador
- 2 OK         → viable_con_ajustes + requires_human_review
- ≤1 OK        → no_viable + "Datos insuficientes"
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from agents.contracts import (
    AgentError,
    AgentResult,
    Confidence,
    SpecialistName,
    Verdict,
)

AGENT_WEIGHTS: dict[SpecialistName, Decimal] = {
    "financiero": Decimal("0.35"),
    "mercado": Decimal("0.25"),
    "riesgo": Decimal("0.20"),
    "estrategia": Decimal("0.20"),
}


def count_ok(
    results: dict[SpecialistName, AgentResult | AgentError],
) -> int:
    return sum(1 for v in results.values() if isinstance(v, AgentResult))


def weighted_final_score(
    results: dict[SpecialistName, AgentResult | AgentError],
) -> int:
    """Promedio ponderado normalizado sobre agentes válidos.

    Si financiero falla pero los otros 3 OK, los pesos se renormalizan
    sobre {mercado, riesgo, estrategia} = 0.65 total.
    """
    valid = {k: v for k, v in results.items() if isinstance(v, AgentResult)}
    if not valid:
        return 0

    total_weight = sum(AGENT_WEIGHTS[k] for k in valid)
    if total_weight == 0:
        return 0

    weighted_sum = sum(AGENT_WEIGHTS[k] * v.score for k, v in valid.items())
    return int(
        (weighted_sum / total_weight).to_integral_value(rounding=ROUND_HALF_UP)
    )


def degraded_verdict(
    results: dict[SpecialistName, AgentResult | AgentError],
    final_score: int,
) -> tuple[Verdict, bool, Confidence]:
    """Decide veredicto cuando hay fallos parciales.

    Retorna (veredicto, requires_human_review, confidence).
    Solo aplica para casos extremos (≤2 agentes OK). Para ≥3 OK el orquestador
    decide vía LLM y este helper no se usa.
    """
    ok = count_ok(results)
    if ok <= 1:
        return "no_viable", True, "low"
    if ok == 2:
        return "viable_con_ajustes", True, "low"
    raise ValueError(
        f"degraded_verdict no debe llamarse con {ok} agentes OK (use LLM)"
    )


def verdict_from_score(score: int) -> Verdict:
    """Mapeo score → veredicto. Solo fallback si el LLM no decide.

    Umbrales conservadores: prefiere viable_con_ajustes sobre viable.
    """
    if score >= 75:
        return "viable"
    if score >= 50:
        return "viable_con_ajustes"
    return "no_viable"
