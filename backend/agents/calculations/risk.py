"""Pre-cálculos de riesgo con heurísticas de dominio mexicano."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict

from agents.contracts import EvaluationInputs

ZERO = Decimal("0")
HUNDRED = Decimal("100")

TC_EXPOSURE_HIGH = Decimal("40")
TC_EXPOSURE_MEDIUM = Decimal("20")

CONCENTRATION_THRESHOLD = Decimal("50")

MARGIN_SAFETY_CRITICAL = Decimal("5")
MARGIN_SAFETY_LOW = Decimal("15")


class RiskCalcs(BaseModel):
    model_config = ConfigDict(frozen=True)

    tc_exposure_pct: Decimal
    cost_concentration: str
    dominant_cost_name: str | None
    margin_safety_tc: Decimal
    risk_flags: list[str]


def _r2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _total_cost(inputs: EvaluationInputs) -> Decimal:
    return (
        inputs.cost_purchase
        + inputs.cost_freight
        + inputs.cost_customs
        + inputs.cost_storage
        + inputs.cost_logistics_vehicle
        + inputs.cost_logistics_viaticos
        + inputs.cost_logistics_personnel
        + inputs.cost_marketing
        + inputs.cost_overhead
    )


def _tc_exposure(inputs: EvaluationInputs, total: Decimal) -> Decimal:
    if inputs.cost_purchase_usd is None or inputs.cost_purchase_usd <= 0:
        return ZERO
    if total <= 0:
        return ZERO
    usd_in_mxn = inputs.cost_purchase_usd * inputs.exchange_rate_used
    return _r2(usd_in_mxn / total * HUNDRED)


def _cost_breakdown(inputs: EvaluationInputs) -> dict[str, Decimal]:
    return {
        "cost_purchase": inputs.cost_purchase,
        "cost_freight": inputs.cost_freight,
        "cost_customs": inputs.cost_customs,
        "cost_storage": inputs.cost_storage,
        "cost_logistics_vehicle": inputs.cost_logistics_vehicle,
        "cost_logistics_viaticos": inputs.cost_logistics_viaticos,
        "cost_logistics_personnel": inputs.cost_logistics_personnel,
        "cost_marketing": inputs.cost_marketing,
        "cost_overhead": inputs.cost_overhead,
    }


def _concentration(breakdown: dict[str, Decimal], total: Decimal) -> tuple[str, str | None]:
    if total <= 0:
        return "disperso", None
    max_name = max(breakdown, key=breakdown.get)  # type: ignore[arg-type]
    max_pct = breakdown[max_name] / total * HUNDRED
    if max_pct >= CONCENTRATION_THRESHOLD:
        return "concentrado", max_name
    if max_pct >= Decimal("30"):
        return "moderado", max_name
    return "disperso", None


def _margin_safety_tc(inputs: EvaluationInputs) -> Decimal:
    if inputs.cost_purchase_usd is None or inputs.cost_purchase_usd <= 0:
        return Decimal("99.99")

    tc = inputs.exchange_rate_used
    price = inputs.target_price
    base_cost = _total_cost(inputs)
    units = Decimal(inputs.estimated_units_month)
    base_per_unit = base_cost / units if units > 0 else base_cost
    base_margin = price - base_per_unit

    if base_margin <= 0:
        return ZERO

    usd_cost = inputs.cost_purchase_usd
    lo, hi = Decimal("0"), Decimal("200")
    for _ in range(50):
        mid = (lo + hi) / 2
        new_tc = tc * (1 + mid / HUNDRED)
        tc_delta = (new_tc - tc) * usd_cost
        new_margin = base_margin - tc_delta
        if new_margin <= 0:
            hi = mid
        else:
            lo = mid
    return _r2(lo)


def calculate_risk(inputs: EvaluationInputs) -> RiskCalcs:
    total = _total_cost(inputs)
    tc_exp = _tc_exposure(inputs, total)
    breakdown = _cost_breakdown(inputs)
    concentration, dominant = _concentration(breakdown, total)
    safety = _margin_safety_tc(inputs)

    flags: list[str] = []
    if tc_exp >= TC_EXPOSURE_HIGH:
        flags.append("risk_tc_high")
    elif tc_exp >= TC_EXPOSURE_MEDIUM:
        flags.append("risk_tc_medium")

    if concentration == "concentrado":
        flags.append("risk_single_cost_dominant")

    if safety < MARGIN_SAFETY_CRITICAL:
        flags.append("risk_thin_margin")
    elif safety < MARGIN_SAFETY_LOW:
        flags.append("risk_low_margin_buffer")

    return RiskCalcs(
        tc_exposure_pct=tc_exp,
        cost_concentration=concentration,
        dominant_cost_name=dominant,
        margin_safety_tc=safety,
        risk_flags=flags,
    )
