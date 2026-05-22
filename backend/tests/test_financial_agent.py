import pytest
from agents.financial import calculate_financials, score_from_calculations
from agents.schemas import EvaluationInputs


def make_inputs(**overrides) -> EvaluationInputs:
    base: EvaluationInputs = {
        "product_name": "Producto Test",
        "description": "Descripción",
        "category": "fisico",
        "cost_purchase": 500.0,
        "cost_purchase_usd": 25.0,
        "cost_freight": 80.0,
        "cost_customs": 50.0,
        "cost_storage": 600.0,
        "cost_logistics_vehicle": 100.0,
        "cost_logistics_viaticos": 50.0,
        "cost_logistics_personnel": 150.0,
        "cost_shrinkage_pct": 2.0,
        "cost_commission_pct": 10.0,
        "cost_marketing": 1000.0,
        "cost_overhead": 500.0,
        "target_price": 1200.0,
        "estimated_units_month": 50,
        "sales_channel": "marketplace",
        "exchange_rate": 19.50,
    }
    base.update(overrides)
    return base


def test_gross_margin_calculated_correctly():
    inputs = make_inputs()
    calcs = calculate_financials(inputs)
    # gross = (1200 - 500 - 80 - 50) / 1200 * 100 = 47.5%
    assert abs(calcs["gross_margin_pct"] - 47.5) < 0.01


def test_total_logistics_sum():
    inputs = make_inputs()
    calcs = calculate_financials(inputs)
    assert calcs["total_logistics"] == 300.0  # 100+50+150


def test_monthly_revenue():
    inputs = make_inputs()
    calcs = calculate_financials(inputs)
    assert calcs["monthly_revenue"] == 60000.0  # 1200 * 50


def test_profitable_product():
    inputs = make_inputs()
    calcs = calculate_financials(inputs)
    assert calcs["is_profitable"] == (calcs["monthly_profit"] > 0)


def test_unprofitable_product():
    inputs = make_inputs(cost_purchase=1100.0)
    calcs = calculate_financials(inputs)
    assert calcs["is_profitable"] is False


def test_break_even_units_positive():
    inputs = make_inputs()
    calcs = calculate_financials(inputs)
    assert calcs["break_even_units"] > 0


def test_score_range():
    inputs = make_inputs()
    calcs = calculate_financials(inputs)
    score = score_from_calculations(calcs)
    assert 0 <= score <= 100


def test_score_low_for_unprofitable():
    inputs = make_inputs(cost_purchase=1100.0)
    calcs = calculate_financials(inputs)
    score = score_from_calculations(calcs)
    assert score < 40
