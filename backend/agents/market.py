"""Agente Mercado — análisis de mercado con pre-cálculos de competitividad."""

from agents.base import build_agent
from agents.calculations.market import calculate_market

market_agent = build_agent(
    name="mercado",
    prompt_name="market",
    calc_fn=calculate_market,
)
