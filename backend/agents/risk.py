"""Agente Riesgo. LLM-driven score."""

from agents.base import build_agent

risk_agent = build_agent(
    name="riesgo",
    prompt_name="risk",
)
