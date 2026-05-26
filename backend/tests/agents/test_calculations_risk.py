"""Tests puros para calculations/risk.py — cero LLM, cero IO."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from agents.calculations.risk import RiskCalcs, calculate_risk
from agents.contracts import EvaluationInputs


def _make_inputs(**overrides) -> EvaluationInputs:
    base = dict(
        product_name="Widget Test",
        category="fisico",
        cost_purchase=Decimal("100.00"),
        cost_purchase_usd=Decimal("5.00"),
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


class TestCalculateRisk:
    def test_returns_risk_calcs(self):
        result = calculate_risk(_make_inputs())
        assert isinstance(result, RiskCalcs)

    def test_tc_exposure_with_usd_cost(self):
        result = calculate_risk(_make_inputs(
            cost_purchase_usd=Decimal("5.00"),
            exchange_rate_used=Decimal("20.00"),
        ))
        assert result.tc_exposure_pct > Decimal("0")

    def test_tc_exposure_zero_without_usd(self):
        result = calculate_risk(_make_inputs(cost_purchase_usd=None))
        assert result.tc_exposure_pct == Decimal("0")

    def test_high_tc_exposure_flag(self):
        result = calculate_risk(_make_inputs(
            cost_purchase=Decimal("200.00"),
            cost_purchase_usd=Decimal("10.00"),
            exchange_rate_used=Decimal("20.00"),
            cost_freight=Decimal("0"),
            cost_customs=Decimal("0"),
            cost_storage=Decimal("0"),
            cost_logistics_vehicle=Decimal("0"),
            cost_logistics_viaticos=Decimal("0"),
            cost_logistics_personnel=Decimal("0"),
            cost_marketing=Decimal("0"),
            cost_overhead=Decimal("0"),
        ))
        assert result.tc_exposure_pct >= Decimal("40")
        assert "risk_tc_high" in result.risk_flags

    def test_cost_concentration_concentrated(self):
        result = calculate_risk(_make_inputs(
            cost_purchase=Decimal("500.00"),
            cost_freight=Decimal("1.00"),
            cost_customs=Decimal("1.00"),
            cost_storage=Decimal("1.00"),
            cost_logistics_vehicle=Decimal("0"),
            cost_logistics_viaticos=Decimal("0"),
            cost_logistics_personnel=Decimal("0"),
            cost_marketing=Decimal("1.00"),
            cost_overhead=Decimal("1.00"),
        ))
        assert result.cost_concentration == "concentrado"
        assert result.dominant_cost_name == "cost_purchase"

    def test_margin_safety_tc_positive(self):
        result = calculate_risk(_make_inputs())
        assert result.margin_safety_tc >= Decimal("0")

    def test_no_usd_margin_safety_max(self):
        result = calculate_risk(_make_inputs(cost_purchase_usd=None))
        assert result.margin_safety_tc == Decimal("99.99")

    def test_risk_flags_list_type(self):
        result = calculate_risk(_make_inputs())
        assert isinstance(result.risk_flags, list)

    def test_concentration_dispersed_when_even(self):
        result = calculate_risk(_make_inputs(
            cost_purchase=Decimal("20.00"),
            cost_freight=Decimal("20.00"),
            cost_customs=Decimal("20.00"),
            cost_storage=Decimal("20.00"),
            cost_logistics_vehicle=Decimal("0"),
            cost_logistics_viaticos=Decimal("0"),
            cost_logistics_personnel=Decimal("0"),
            cost_marketing=Decimal("20.00"),
            cost_overhead=Decimal("20.00"),
        ))
        assert result.cost_concentration in ("disperso", "moderado")
