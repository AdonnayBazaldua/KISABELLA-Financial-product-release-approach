"""Agente Estrategia Comercial. LLM-driven score."""

from agents.base import build_agent

strategy_agent = build_agent(
    name="estrategia",
    prompt_name="strategy",
)
