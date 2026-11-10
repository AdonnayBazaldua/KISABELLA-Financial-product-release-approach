"""Pipeline LangGraph: fan-out a 4 agentes → fan-in al orquestador.

ADR-001/002: state.agent_results es dict[name, AgentResult|AgentError].
Cada agente corre en su nodo. Si falla, se captura en AgentError — el pipeline
NO se aborta (graceful degradation).

Timeouts (ADR del workflow tree):
- Por agente: 90s vía asyncio.wait_for.
- Global del pipeline: orquestado por el llamador (BackgroundTask con timeout).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from langgraph.graph import END, START, StateGraph

from agents.base import AgentFn
from agents.contracts import (
    AgentError,
    AgentResult,
    EvaluationInputs,
    PipelineState,
    SpecialistName,
    TCMetadata,
)
from agents.financial import financial_agent
from agents.llm_client import BudgetedLLMClient, LLMClient
from agents.market import market_agent
from agents.orchestrator import build_orchestrator_node
from agents.risk import risk_agent
from agents.strategy import strategy_agent

AGENT_TIMEOUT_S = 90

AGENTS: dict[SpecialistName, AgentFn] = {
    "financiero": financial_agent,
    "mercado": market_agent,
    "riesgo": risk_agent,
    "estrategia": strategy_agent,
}


def _wrap_agent_node(
    name: SpecialistName, agent_fn: AgentFn, llm: LLMClient
) -> Any:
    """Wrap async agent_fn en nodo LangGraph con timeout + error handling + logging."""
    log = structlog.get_logger()

    async def _node(state: PipelineState) -> dict:
        eval_id = str(state.get("eval_id", ""))
        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(
                agent_fn(state["inputs"], llm), timeout=AGENT_TIMEOUT_S
            )
            log.info(
                "agent_complete",
                agent_name=name,
                evaluation_id=eval_id,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
            return {"agent_results": {name: result}, "warn_flags": result.warn_flags}
        except asyncio.TimeoutError:
            log.warning(
                "agent_timeout",
                agent_name=name,
                evaluation_id=eval_id,
                timeout_s=AGENT_TIMEOUT_S,
            )
            return {
                "agent_results": {
                    name: AgentError(
                        agent_name=name,
                        error_type="timeout",
                        error_message=f"Agente {name} excedió {AGENT_TIMEOUT_S}s",
                    )
                }
            }
        except Exception as exc:  # noqa: BLE001
            log.error(
                "agent_error",
                agent_name=name,
                evaluation_id=eval_id,
                error_type="unknown",
                error_message=str(exc)[:200],
            )
            return {
                "agent_results": {
                    name: AgentError(
                        agent_name=name,
                        error_type="unknown",
                        error_message=str(exc)[:1000],
                    )
                }
            }

    _node.__name__ = f"{name}_node"
    return _node


def build_pipeline(llm: LLMClient):
    """Compila el grafo LangGraph paralelo."""
    g = StateGraph(PipelineState)

    for name, agent_fn in AGENTS.items():
        g.add_node(name, _wrap_agent_node(name, agent_fn, llm))
        g.add_edge(START, name)
        g.add_edge(name, "orquestador")

    g.add_node("orquestador", build_orchestrator_node(llm))
    g.add_edge("orquestador", END)

    return g.compile()


async def run_evaluation(
    inputs: EvaluationInputs,
    tc_meta: TCMetadata,
    llm: LLMClient,
    *,
    eval_id=None,
    user_id=None,
    warn_flags: list[str] | None = None,
) -> PipelineState:
    """Helper: corre el pipeline completo y retorna el state final."""
    budgeted = BudgetedLLMClient(llm)
    pipeline = build_pipeline(budgeted)
    initial: PipelineState = {
        "inputs": inputs,
        "tc_meta": tc_meta,
        "agent_results": {},
        "warn_flags": list(warn_flags or []),
    }
    if eval_id is not None:
        initial["eval_id"] = eval_id
    if user_id is not None:
        initial["user_id"] = user_id

    return await pipeline.ainvoke(initial)
