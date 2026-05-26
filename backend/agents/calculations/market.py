"""Pre-calculos de mercado con heuristicas de dominio mexicano.

Complementa financial.py con metricas orientadas al agente Mercado:
- Ratio precio/costo (competitividad de precio).
- Margen bruto vs sector tipico mexicano (fisico vs servicio).
- Tier de volumen (bajo/medio/alto).
- Costo unitario total (reutiliza logica de financial.py pero expone solo lo necesario).

Sin LLM, sin I/O. Funciones deterministicas testeables por tabla.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict

from agents.contracts import EvaluationInputs

ZERO = Decimal("0")
HUNDRED = Decimal("100")

PRICE_RATIO_GOOD = Decimal("1.30")
PRICE_RATIO_RISK = Decimal("1.10")

SECTOR_MARGINS: dict[str, Decimal] = {
    "fisico": Decimal("0.25"),
    "servicio": Decimal("0.40"),
}

VOLUME_LOW = 50
VOLUME_HIGH = 500


class MarketCalcs(BaseModel):
    """Outputs deterministicos de calculate_market. Frozen."""

    model_config = ConfigDict(frozen=True)

    price_competitiveness_ratio: Decimal
    margin_vs_sector: str
    volume_tier: str
    total_unit_cost: Decimal


def _r2(d: Decimal) -> Decimal:
    """Redondea a 2 decimales (half up)."""
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _total_unit_cost(inputs: EvaluationInputs) -> Decimal:
    """Calcula costo unitario total incluyendo todos los 11 componentes."""
    units = Decimal(inputs.estimated_units_month)
    logistics = (
        inputs.cost_logistics_vehicle
        + inputs.cost_logistics_viaticos
        + inputs.cost_logistics_personnel
    )
    fixed_per_unit = (
        inputs.cost_storage + inputs.cost_marketing + inputs.cost_overhead
    ) / units
    logistics_per_unit = logistics / units

    acquisition = inputs.cost_purchase + inputs.cost_freight + inputs.cost_customs
    shrinkage = inputs.cost_purchase * inputs.cost_shrinkage_pct / HUNDRED
    commission = inputs.target_price * inputs.cost_commission_pct / HUNDRED

    return _r2(
        acquisition + fixed_per_unit + logistics_per_unit + shrinkage + commission
    )


def calculate_market(inputs: EvaluationInputs) -> MarketCalcs:
    """Computa metricas de mercado para el agente Mercado. Pura, sin red, sin LLM."""

    unit_cost = _total_unit_cost(inputs)
    ratio = _r2(inputs.target_price / unit_cost) if unit_cost > 0 else Decimal("99.99")

    gross_margin_pct = (
        (inputs.target_price - unit_cost) / inputs.target_price * HUNDRED
        if inputs.target_price > 0
        else ZERO
    )

    sector_typical = SECTOR_MARGINS.get(inputs.category, Decimal("0.25"))
    sector_margin_pct = sector_typical * HUNDRED

    if gross_margin_pct > sector_margin_pct + 5:
        margin_vs = "above"
    elif gross_margin_pct < sector_margin_pct - 5:
        margin_vs = "below"
    else:
        margin_vs = "at"

    vol = inputs.estimated_units_month
    if vol < VOLUME_LOW:
        tier = "bajo"
    elif vol <= VOLUME_HIGH:
        tier = "medio"
    else:
        tier = "alto"

    return MarketCalcs(
        price_competitiveness_ratio=ratio,
        margin_vs_sector=margin_vs,
        volume_tier=tier,
        total_unit_cost=unit_cost,
    )
