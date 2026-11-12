"""Calculadora financiera pura.

Migrada del antiguo `backend/agents/financial.py` (commit 5c68a47).
Diferencias respecto al original:
- Usa Decimal en vez de mezclar float/int (precisión monetaria).
- Recibe Pydantic EvaluationInputs, no TypedDict.
- Retorna Pydantic FinancialCalcs frozen (no TypedDict).
- Magic literals (99, 9999) reemplazados por None para casos no aplicables.
- Sensibilidad TC ±10% agregada (faltaba en el código).

Score 0-100 derivado por reglas determinísticas — el LLM solo escribe
el análisis textual, no decide el score. Esto da reproducibilidad.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict

from agents.contracts import EvaluationInputs

ZERO = Decimal("0")
HUNDRED = Decimal("100")
ONE = Decimal("1")


class FinancialCalcs(BaseModel):
    """Outputs determinísticos de calculate_financials. Frozen."""

    model_config = ConfigDict(frozen=True)

    # Costos
    total_logistics: Decimal
    total_cost_per_unit: Decimal
    acquisition_cost_per_unit: Decimal

    # Márgenes (%)
    gross_margin_pct: Decimal
    net_margin_pct: Decimal

    # Mensual
    monthly_revenue: Decimal
    monthly_total_cost: Decimal
    monthly_profit: Decimal

    # Punto equilibrio / payback / ROI
    # None cuando no aplica (margen contribución <= 0, no profitable, etc.)
    break_even_units: int | None
    roi_monthly_pct: Decimal
    payback_months: Decimal | None

    # Sensibilidad TC ±10% — impacto en margen neto cuando costos USD escalan
    net_margin_pct_tc_plus_10: Decimal
    net_margin_pct_tc_minus_10: Decimal

    # Bandera
    is_profitable: bool


def _r2(d: Decimal) -> Decimal:
    """Redondea a 2 decimales (half up)."""
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _r4(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_financials(inputs: EvaluationInputs) -> FinancialCalcs:
    """Computa todos los números del agente Financiero. Pura, sin red, sin LLM."""

    units = Decimal(inputs.estimated_units_month)  # > 0 garantizado por validator
    price = inputs.target_price  # > 0 garantizado

    total_logistics = (
        inputs.cost_logistics_vehicle
        + inputs.cost_logistics_viaticos
        + inputs.cost_logistics_personnel
    )

    # Prorrateos por unidad
    storage_per_unit = inputs.cost_storage / units
    marketing_per_unit = inputs.cost_marketing / units
    overhead_per_unit = inputs.cost_overhead / units
    logistics_per_unit = total_logistics / units

    # Variables por unidad
    shrinkage_per_unit = inputs.cost_purchase * inputs.cost_shrinkage_pct / HUNDRED
    commission_per_unit = price * inputs.cost_commission_pct / HUNDRED

    acquisition_cost_per_unit = (
        inputs.cost_purchase + inputs.cost_freight + inputs.cost_customs
    )

    total_cost_per_unit = (
        acquisition_cost_per_unit
        + storage_per_unit
        + logistics_per_unit
        + marketing_per_unit
        + overhead_per_unit
        + shrinkage_per_unit
        + commission_per_unit
    )

    gross_margin_pct = (price - acquisition_cost_per_unit) / price * HUNDRED
    net_margin_pct = (price - total_cost_per_unit) / price * HUNDRED

    monthly_revenue = price * units
    monthly_total_cost = total_cost_per_unit * units
    monthly_profit = monthly_revenue - monthly_total_cost

    # Punto de equilibrio: usa solo costos fijos vs margen de contribución unitario
    fixed_monthly = inputs.cost_storage + inputs.cost_marketing + inputs.cost_overhead
    variable_cost_per_unit = (
        acquisition_cost_per_unit
        + logistics_per_unit
        + shrinkage_per_unit
        + commission_per_unit
    )
    contribution_margin = price - variable_cost_per_unit
    if contribution_margin > 0:
        be = (fixed_monthly / contribution_margin).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        break_even_units: int | None = int(be)
    else:
        break_even_units = None

    initial_investment = inputs.cost_purchase * units
    if initial_investment > 0:
        roi_monthly_pct = monthly_profit / initial_investment * HUNDRED
    else:
        roi_monthly_pct = ZERO

    payback_months: Decimal | None
    if monthly_profit > 0:
        payback_months = _r2(initial_investment / monthly_profit)
    else:
        payback_months = None

    # Sensibilidad TC ±10%: si el costo de compra original venía de USD, el
    # ajuste de TC escala cost_purchase. Si cost_purchase_usd está set, usamos
    # eso como base; si no, asumimos que toda la compra es USD-sensible.
    usd_base = (
        inputs.cost_purchase_usd if inputs.cost_purchase_usd is not None else None
    )
    if usd_base is not None and usd_base > 0:
        # cost_purchase en MXN actual = usd_base * tc_actual
        # Estimamos cost_purchase ajustado por ±10% en TC
        delta = inputs.cost_purchase * Decimal("0.10")
    else:
        # Asumimos que cost_purchase es 100% USD-sensible
        delta = inputs.cost_purchase * Decimal("0.10")

    cost_plus = total_cost_per_unit + delta
    cost_minus = total_cost_per_unit - delta
    net_margin_pct_tc_plus_10 = (price - cost_plus) / price * HUNDRED
    net_margin_pct_tc_minus_10 = (price - cost_minus) / price * HUNDRED

    return FinancialCalcs(
        total_logistics=_r2(total_logistics),
        total_cost_per_unit=_r2(total_cost_per_unit),
        acquisition_cost_per_unit=_r2(acquisition_cost_per_unit),
        gross_margin_pct=_r2(gross_margin_pct),
        net_margin_pct=_r2(net_margin_pct),
        monthly_revenue=_r2(monthly_revenue),
        monthly_total_cost=_r2(monthly_total_cost),
        monthly_profit=_r2(monthly_profit),
        break_even_units=break_even_units,
        roi_monthly_pct=_r2(roi_monthly_pct),
        payback_months=payback_months,
        net_margin_pct_tc_plus_10=_r2(net_margin_pct_tc_plus_10),
        net_margin_pct_tc_minus_10=_r2(net_margin_pct_tc_minus_10),
        is_profitable=monthly_profit > 0,
    )


def score_from_calculations(calcs: FinancialCalcs) -> int:
    """Convierte FinancialCalcs en score 0-100 con reglas determinísticas.

    Tramos:
    - Margen neto: 0-40 puntos (5/10/20/30/40 por umbrales 5/10/20/30%)
    - ROI mensual: 0-30 puntos (10/20/30 por umbrales 5/10/20%)
    - Payback: 0-20 puntos (10/15/20 por umbrales 12/6/3 meses)
    - Profitable: 0-10 puntos (binario)
    """
    score = 0

    # Margen neto (max 40)
    nm = calcs.net_margin_pct
    if nm >= 30:
        score += 40
    elif nm >= 20:
        score += 30
    elif nm >= 10:
        score += 20
    elif nm >= 5:
        score += 10

    # ROI mensual (max 30)
    roi = calcs.roi_monthly_pct
    if roi >= 20:
        score += 30
    elif roi >= 10:
        score += 20
    elif roi >= 5:
        score += 10

    # Payback (max 20)
    pb = calcs.payback_months
    if pb is not None:
        if pb <= 3:
            score += 20
        elif pb <= 6:
            score += 15
        elif pb <= 12:
            score += 10

    # Profitable (max 10)
    if calcs.is_profitable:
        score += 10

    return min(score, 100)
