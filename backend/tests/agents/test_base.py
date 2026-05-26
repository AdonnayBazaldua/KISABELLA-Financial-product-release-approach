"""Tests para agents.base — load_prompt + build_agent."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from agents.base import build_agent, load_prompt
from agents.calculations.market import calculate_market
from agents.contracts import AgentResult, EvaluationInputs
from agents.llm_client import FakeLLMClient


def _make_inputs(**overrides) -> EvaluationInputs:
    base = dict(
        product_name="Producto Test",
        category="fisico",
        cost_purchase=Decimal("100.00"),
        cost_freight=Decimal("10.00"),
        cost_customs=Decimal("15.00"),
        cost_storage=Decimal("0.00"),
        cost_logistics_vehicle=Decimal("0.00"),
        cost_logistics_viaticos=Decimal("0.00"),
        cost_logistics_personnel=Decimal("0.00"),
        cost_shrinkage_pct=Decimal("0.00"),
        cost_commission_pct=Decimal("0.00"),
        cost_marketing=Decimal("0.00"),
        cost_overhead=Decimal("0.00"),
        target_price=Decimal("200.00"),
        estimated_units_month=100,
        exchange_rate_used=Decimal("19.8500"),
        exchange_rate_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return EvaluationInputs(**base)


def _make_agent_result(score: int = 75) -> AgentResult:
    return AgentResult(
        score=score,
        veredicto_corto="veredicto valido para test",
        analisis_extenso="x" * 400,
        hallazgos_clave=["hallazgo de prueba"],
        recomendaciones=["recomendacion de prueba"],
    )


class TestLoadPrompt:
    def test_loads_existing_prompt(self):
        p = load_prompt("financial")
        assert "analista financiero" in p.system.lower()
        assert "{product_name}" in p.user_template

    def test_raises_on_missing(self):
        with pytest.raises(FileNotFoundError):
            load_prompt("inexistente")

    def test_separates_system_and_user_template(self):
        p = load_prompt("market")
        assert p.system != p.user_template
        assert len(p.system) > 0
        assert len(p.user_template) > 0


class TestBuildAgent:
    async def test_calls_llm_with_rendered_user(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _make_agent_result(score=70))

        agent = build_agent(name="test", prompt_name="market", calc_fn=calculate_market)
        result = await agent(_make_inputs(product_name="Test Producto"), fake)

        assert isinstance(result, AgentResult)
        assert len(fake.calls) == 1
        # Product_name rendered in user msg
        assert "Test Producto" in fake.calls[0].user

    async def test_score_fn_overrides_llm_score(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _make_agent_result(score=10))

        def always_99(_raw, _calc):
            return 99

        agent = build_agent(
            name="test",
            prompt_name="market",
            calc_fn=calculate_market,
            score_fn=always_99,
        )
        result = await agent(_make_inputs(), fake)

        assert result.score == 99

    async def test_no_score_fn_uses_llm_score(self):
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _make_agent_result(score=42))

        agent = build_agent(name="test", prompt_name="market", calc_fn=calculate_market)
        result = await agent(_make_inputs(), fake)

        assert result.score == 42

    async def test_calc_fn_output_injected_in_template(self):
        from pydantic import BaseModel, ConfigDict

        class FakeCalc(BaseModel):
            model_config = ConfigDict(frozen=True)
            acquisition_cost_per_unit: Decimal = Decimal("125.00")
            total_cost_per_unit: Decimal = Decimal("125.00")
            gross_margin_pct: Decimal = Decimal("37.50")
            net_margin_pct: Decimal = Decimal("37.50")
            monthly_revenue: Decimal = Decimal("20000.00")
            monthly_profit: Decimal = Decimal("7500.00")
            roi_monthly_pct: Decimal = Decimal("75.00")
            break_even_units: int = 0
            payback_months: Decimal = Decimal("1.33")
            net_margin_pct_tc_plus_10: Decimal = Decimal("32.50")
            net_margin_pct_tc_minus_10: Decimal = Decimal("42.50")
            is_profitable: bool = True

        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _make_agent_result())

        agent = build_agent(
            name="test",
            prompt_name="financial",
            calc_fn=lambda _i: FakeCalc(),
        )
        await agent(_make_inputs(), fake)

        user_msg = fake.calls[0].user
        # Verificar que el calc se inyectó
        assert "37.50" in user_msg  # gross_margin_pct
        assert "1.33" in user_msg  # payback_months


class TestRenderingNoneValues:
    async def test_none_becomes_nd(self):
        """break_even_units = None debe renderizarse como 'N/D'."""
        fake = FakeLLMClient()
        fake.set_response_for(AgentResult, _make_agent_result())

        from agents.calculations.financial import calculate_financials

        # target_price = cost → no profitable → break_even None
        bad_inputs = _make_inputs(target_price=Decimal("125.00"))

        agent = build_agent(
            name="test",
            prompt_name="financial",
            calc_fn=calculate_financials,
        )
        await agent(bad_inputs, fake)

        user_msg = fake.calls[0].user
        assert "N/D" in user_msg
