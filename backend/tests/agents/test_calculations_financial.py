"""Tests para agents.calculations.financial — calculadora pura."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from agents.calculations.financial import (
    FinancialCalcs,
    calculate_financials,
    score_from_calculations,
)
from agents.contracts import EvaluationInputs


def _eval(**overrides) -> EvaluationInputs:
    base = dict(
        product_name="Test",
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


class TestBasicMargen:
    """Caso minimalista: solo compra+flete+aduana, sin variables ni overhead."""

    def test_acquisition_cost_per_unit(self):
        c = calculate_financials(_eval())
        # 100 + 10 + 15
        assert c.acquisition_cost_per_unit == Decimal("125.00")

    def test_total_cost_per_unit(self):
        # Sin variables ni prorrateos
        c = calculate_financials(_eval())
        assert c.total_cost_per_unit == Decimal("125.00")

    def test_gross_margin_pct(self):
        # (200 - 125) / 200 = 37.5%
        c = calculate_financials(_eval())
        assert c.gross_margin_pct == Decimal("37.50")

    def test_net_margin_pct(self):
        c = calculate_financials(_eval())
        assert c.net_margin_pct == Decimal("37.50")

    def test_monthly_revenue(self):
        # 200 * 100
        c = calculate_financials(_eval())
        assert c.monthly_revenue == Decimal("20000.00")

    def test_monthly_profit(self):
        # 20000 - 12500 = 7500
        c = calculate_financials(_eval())
        assert c.monthly_profit == Decimal("7500.00")

    def test_is_profitable(self):
        c = calculate_financials(_eval())
        assert c.is_profitable is True


class TestPercentages:
    def test_shrinkage_reduces_margin(self):
        c = calculate_financials(_eval(cost_shrinkage_pct=Decimal("5.00")))
        # Shrinkage = 100 * 5% = 5 per unit
        # Total = 125 + 5 = 130
        assert c.total_cost_per_unit == Decimal("130.00")

    def test_commission_reduces_margin(self):
        c = calculate_financials(_eval(cost_commission_pct=Decimal("10.00")))
        # Commission = 200 * 10% = 20 per unit
        # Total = 125 + 20 = 145
        assert c.total_cost_per_unit == Decimal("145.00")


class TestFixedCostsProrrateados:
    def test_storage_prorrateado(self):
        # storage 1000 / 100 units = 10 per unit
        c = calculate_financials(_eval(cost_storage=Decimal("1000.00")))
        assert c.total_cost_per_unit == Decimal("135.00")  # 125 + 10

    def test_overhead_prorrateado(self):
        c = calculate_financials(_eval(cost_overhead=Decimal("500.00")))
        # 500 / 100 = 5 per unit
        assert c.total_cost_per_unit == Decimal("130.00")


class TestPaybackAndROI:
    def test_payback_profitable(self):
        c = calculate_financials(_eval())
        # initial_investment = 100 * 100 = 10000
        # monthly_profit = 7500
        # payback = 10000 / 7500 = 1.33
        assert c.payback_months == Decimal("1.33")

    def test_roi_monthly_positive(self):
        c = calculate_financials(_eval())
        # 7500 / 10000 * 100 = 75%
        assert c.roi_monthly_pct == Decimal("75.00")

    def test_payback_none_when_not_profitable(self):
        # Costo igual a precio → profit = 0 → no payback
        c = calculate_financials(_eval(target_price=Decimal("125.00")))
        assert c.payback_months is None
        assert c.is_profitable is False

    def test_payback_none_when_loss(self):
        c = calculate_financials(_eval(target_price=Decimal("100.00")))
        assert c.is_profitable is False
        assert c.payback_months is None
        assert c.monthly_profit < 0


class TestBreakEven:
    def test_break_even_zero_fixed(self):
        # Sin costos fijos -> equilibrio en 0 unidades
        c = calculate_financials(_eval())
        assert c.break_even_units == 0

    def test_break_even_with_fixed(self):
        # fixed = 1000 (storage)
        # contribution per unit = price - variable_cost
        # variable = 125 (acquisition only, sin pct ni prorrateo de fijos)
        # contribution = 200 - 125 = 75
        # BE = 1000 / 75 ≈ 13.33 → 13 redondeado
        c = calculate_financials(_eval(cost_storage=Decimal("1000.00")))
        assert c.break_even_units == 13

    def test_break_even_none_when_no_contribution(self):
        # price <= variable cost → contribución <= 0
        c = calculate_financials(_eval(target_price=Decimal("100.00")))
        assert c.break_even_units is None


class TestSensibilidadTC:
    def test_plus_10_reduces_margin(self):
        c = calculate_financials(_eval())
        # +10% en costo compra (100 -> 110, delta=10) reduce margen
        assert c.net_margin_pct_tc_plus_10 < c.net_margin_pct

    def test_minus_10_increases_margin(self):
        c = calculate_financials(_eval())
        assert c.net_margin_pct_tc_minus_10 > c.net_margin_pct

    def test_symmetric_around_base(self):
        c = calculate_financials(_eval())
        # Delta debe ser simétrico (porque es lineal sobre cost_purchase)
        delta_plus = c.net_margin_pct - c.net_margin_pct_tc_plus_10
        delta_minus = c.net_margin_pct_tc_minus_10 - c.net_margin_pct
        assert delta_plus == delta_minus


class TestImmutability:
    def test_calcs_is_frozen(self):
        c = calculate_financials(_eval())
        with pytest.raises(Exception):
            c.net_margin_pct = Decimal("99.99")  # type: ignore[misc]


class TestScoreFromCalculations:
    def test_excellent_case_max_score(self):
        # Margen 37.5% (40 pts), ROI 75% (30 pts), Payback 1.33m (20 pts), profitable (10 pts) = 100
        c = calculate_financials(_eval())
        assert score_from_calculations(c) == 100

    def test_zero_margin_minimum(self):
        # price = acquisition → margen 0%, profit 0, no payback
        c = calculate_financials(_eval(target_price=Decimal("125.00")))
        assert score_from_calculations(c) == 0

    def test_score_in_range_0_100(self):
        for price in (Decimal("130"), Decimal("150"), Decimal("200"), Decimal("400")):
            c = calculate_financials(_eval(target_price=price))
            s = score_from_calculations(c)
            assert 0 <= s <= 100

    def test_mediocre_case_partial_score(self):
        # Margen 10% justo: 10pts margen + 0 ROI (necesita >=5%) + 0 payback + 10 profitable
        # acquisition = 125, price = 138.89 → margen = (138.89 - 125)/138.89 ≈ 10%
        c = calculate_financials(_eval(target_price=Decimal("139.00")))
        s = score_from_calculations(c)
        # ROI mensual depende: profit ≈ 14 * 100 = 1400, inv = 10000 → ROI 14% → 20pts
        # Total: margen 20 (10-20%) + ROI 20 + payback 10 (7m) + profitable 10 = 60
        assert 40 <= s <= 80
