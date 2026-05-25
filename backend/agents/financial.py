"""Agente Financiero — análisis cualitativo + score determinístico."""

from agents.base import build_agent
from agents.calculations.financial import (
    FinancialCalcs,
    calculate_financials,
    score_from_calculations,
)
from agents.contracts import AgentResult


def _score_override(_raw: AgentResult, calc: FinancialCalcs) -> int:
    """Reemplaza el score del LLM con score_from_calculations (determinístico)."""
    return score_from_calculations(calc)


financial_agent = build_agent(
    name="financiero",
    prompt_name="financial",
    calc_fn=calculate_financials,
    score_fn=_score_override,
)
