"""Tests puros para calculations/market.py -- cero LLM, cero IO."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from agents.calculations.market import MarketCalcs, calculate_market
from agents.contracts import EvaluationInputs


def _make_inputs(**overrides) -> EvaluationInputs:
    base = dict(
        product_name="Widget Test",
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


class TestCalculateMarket:
    def test_returns_market_calcs(self):
        result = calculate_market(_make_inputs())
        assert isinstance(result, MarketCalcs)

    def test_price_competitiveness_high_margin(self):
        result = calculate_market(_make_inputs(target_price=Decimal("500.00")))
        assert result.price_competitiveness_ratio > Decimal("1.30")

    def test_price_competitiveness_low_margin(self):
        result = calculate_market(_make_inputs(target_price=Decimal("145.00")))
        assert result.price_competitiveness_ratio < Decimal("1.10")

    def test_price_equals_cost_ratio_near_one(self):
        inputs = _make_inputs(
            target_price=Decimal("165.00"),
            cost_purchase=Decimal("100.00"),
            cost_freight=Decimal("10.00"),
            cost_customs=Decimal("15.00"),
            cost_storage=Decimal("5.00"),
            cost_logistics_vehicle=Decimal("3.00"),
            cost_logistics_viaticos=Decimal("2.00"),
            cost_logistics_personnel=Decimal("5.00"),
            cost_shrinkage_pct=Decimal("0.00"),
            cost_commission_pct=Decimal("0.00"),
            cost_marketing=Decimal("10.00"),
            cost_overhead=Decimal("10.00"),
            estimated_units_month=1,
        )
        result = calculate_market(inputs)
        assert Decimal("0.95") <= result.price_competitiveness_ratio <= Decimal("1.15")

    def test_margin_vs_sector_above(self):
        result = calculate_market(_make_inputs(target_price=Decimal("500.00")))
        assert result.margin_vs_sector == "above"

    def test_margin_vs_sector_below(self):
        result = calculate_market(_make_inputs(target_price=Decimal("145.00")))
        assert result.margin_vs_sector == "below"

    def test_volume_tier_bajo(self):
        result = calculate_market(_make_inputs(estimated_units_month=10))
        assert result.volume_tier == "bajo"

    def test_volume_tier_medio(self):
        result = calculate_market(_make_inputs(estimated_units_month=200))
        assert result.volume_tier == "medio"

    def test_volume_tier_alto(self):
        result = calculate_market(_make_inputs(estimated_units_month=1000))
        assert result.volume_tier == "alto"

    def test_total_unit_cost_positive(self):
        result = calculate_market(_make_inputs())
        assert result.total_unit_cost > 0
