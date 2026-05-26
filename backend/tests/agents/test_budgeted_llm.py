"""Tests para BudgetedLLMClient — enforcement de caps por evaluación."""

import pytest

from agents.contracts import AgentResult
from agents.llm_client import BudgetedLLMClient, BudgetExhaustedError, FakeLLMClient


def _agent_result(score: int = 75) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="veredicto valido para test budgeted",
        analisis_extenso="x" * 400,
        hallazgos_clave=["hallazgo"],
        recomendaciones=["recomendacion"],
    )


class TestBudgetedLLMClient:
    async def test_calls_within_budget_succeed(self):
        fake = FakeLLMClient()
        fake.queue_responses([_agent_result() for _ in range(4)])
        budgeted = BudgetedLLMClient(fake, max_calls=6, max_input_tokens=20_000)

        for _ in range(4):
            await budgeted.request_structured(
                system="short system", user="short user", schema=AgentResult
            )

        assert budgeted.budget_summary["calls_used"] == 4

    async def test_exceeds_max_calls_raises(self):
        fake = FakeLLMClient()
        fake.queue_responses([_agent_result() for _ in range(3)])
        budgeted = BudgetedLLMClient(fake, max_calls=2, max_input_tokens=20_000)

        await budgeted.request_structured(system="s", user="u", schema=AgentResult)
        await budgeted.request_structured(system="s", user="u", schema=AgentResult)

        with pytest.raises(BudgetExhaustedError, match="calls"):
            await budgeted.request_structured(system="s", user="u", schema=AgentResult)

    async def test_exceeds_max_tokens_raises(self):
        fake = FakeLLMClient()
        fake.queue_responses([_agent_result()])
        budgeted = BudgetedLLMClient(fake, max_calls=10, max_input_tokens=10)

        with pytest.raises(BudgetExhaustedError, match="tokens"):
            await budgeted.request_structured(
                system="a" * 100, user="b" * 100, schema=AgentResult
            )

    async def test_budget_summary_reflects_usage(self):
        fake = FakeLLMClient()
        fake.queue_responses([_agent_result()])
        budgeted = BudgetedLLMClient(fake, max_calls=6, max_input_tokens=20_000)

        await budgeted.request_structured(
            system="system prompt here", user="user message here", schema=AgentResult
        )

        summary = budgeted.budget_summary
        assert summary["calls_used"] == 1
        assert summary["calls_max"] == 6
        assert summary["tokens_estimated"] > 0
        assert summary["tokens_max"] == 20_000

    async def test_inner_client_receives_all_args(self):
        fake = FakeLLMClient()
        fake.queue_responses([_agent_result()])
        budgeted = BudgetedLLMClient(fake, max_calls=6, max_input_tokens=20_000)

        await budgeted.request_structured(
            system="sys", user="usr", schema=AgentResult, temperature=0.5
        )

        assert len(fake.calls) == 1
        assert fake.calls[0].system == "sys"
        assert fake.calls[0].user == "usr"
        assert fake.calls[0].temperature == 0.5
