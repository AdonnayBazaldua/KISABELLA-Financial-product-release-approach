"""Agente Riesgo — análisis de riesgo con indicadores pre-calculados."""

from agents.base import build_agent
from agents.calculations.risk import calculate_risk

risk_agent = build_agent(
    name="riesgo",
    prompt_name="risk",
    calc_fn=calculate_risk,
)
