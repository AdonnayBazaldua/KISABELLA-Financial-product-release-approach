"""Agente Mercado — análisis de mercado con búsqueda web real (Tavily) + pre-cálculos."""
from agents.base import build_agent
from agents.calculations.market import calculate_market
from agents.contracts import EvaluationInputs
from agents.tools.tavily import search_web


async def _market_tool(inputs: EvaluationInputs) -> str:
    return await search_web(
        f"{inputs.product_name} mercado México precio competencia"
    )


market_agent = build_agent(
    name="mercado",
    prompt_name="market",
    calc_fn=calculate_market,
    tool_fn=_market_tool,
)
