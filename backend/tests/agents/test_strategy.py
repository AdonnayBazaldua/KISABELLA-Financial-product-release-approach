"""Tests del agente Estrategia con FakeLLMClient — sin calc_fn."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from agents.contracts import AgentResult, EvaluationInputs
from agents.llm_client import FakeLLMClient
from agents.strategy import strategy_agent


def _make_inputs(**overrides) -> EvaluationInputs:
    base = dict(
        product_name="Widget Estrategia",
        category="fisico",
        cost_purchase=Decimal("100.00"),
        cost_freight=Decimal("10.00"),
        cost_customs=Decimal("15.00"),
        cost_storage=Decimal("5.00"),
        cost_logistics_vehicle=Decimal("3.00"),
        cost_logistics_viaticos=Decimal("2.00"),
        cost_logistics_personnel=Decimal("5.00"),
        cost_shrinkage_pct=Decimal("2.00"),
        cost_commission_pct=Decimal("5.00"),
        cost_marketing=Decimal("10.00"),
        cost_overhead=Decimal("10.00"),
        target_price=Decimal("250.00"),
        estimated_units_month=100,
        exchange_rate_used=Decimal("19.50"),
        exchange_rate_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
        tc_source="user_provided",
    )
    base.update(overrides)
    return EvaluationInputs(**base)


def _agent_result(score: int = 70) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="estrategia comercial viable con ajustes",
        analisis_extenso="s" * 400,
        hallazgos_clave=["hallazgo estrategia"],
        recomendaciones=["recomendacion estrategia"],
    )


class TestStrategyAgent:
    async def test_returns_agent_result(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _agent_result())
        result = await strategy_agent(_make_inputs(), fake)
        assert isinstance(result, AgentResult)

    async def test_score_from_llm(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _agent_result(score=80))
        result = await strategy_agent(_make_inputs(), fake)
        assert result.score == 80

    async def test_product_name_in_prompt(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _agent_result())
        await strategy_agent(_make_inputs(product_name="Producto Estratégico"), fake)
        assert "Producto Estratégico" in fake.calls[0].user

    async def test_sales_channel_in_prompt(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _agent_result())
        await strategy_agent(_make_inputs(sales_channel="marketplace"), fake)
        assert "marketplace" in fake.calls[0].user

    async def test_cost_purchase_in_prompt(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _agent_result())
        await strategy_agent(_make_inputs(), fake)
        assert "100" in fake.calls[0].user

    async def test_one_llm_call(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _agent_result())
        await strategy_agent(_make_inputs(), fake)
        assert len(fake.calls) == 1
