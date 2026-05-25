"""Agente Mercado — stub Sprint 1 (Tavily se integra en Sprint 6).

El LLM decide el score (sin score_fn determinístico, a diferencia del Financiero).
"""

from agents.base import build_agent

market_agent = build_agent(
    name="mercado",
    prompt_name="market",
)
