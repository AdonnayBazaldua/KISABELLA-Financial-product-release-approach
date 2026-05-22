from typing import TypedDict, Optional


class EvaluationInputs(TypedDict):
    product_name: str
    description: str
    category: str
    # costos en MXN
    cost_purchase: float
    cost_purchase_usd: float
    cost_freight: float
    cost_customs: float
    cost_storage: float           # mensual
    cost_logistics_vehicle: float
    cost_logistics_viaticos: float
    cost_logistics_personnel: float
    cost_shrinkage_pct: float     # porcentaje
    cost_commission_pct: float    # porcentaje sobre precio venta
    cost_marketing: float         # mensual
    cost_overhead: float          # mensual
    target_price: float
    estimated_units_month: int
    sales_channel: str
    exchange_rate: float


class FinancialCalculations(TypedDict):
    total_logistics: float
    total_cost_per_unit: float
    gross_margin_pct: float
    net_margin_pct: float
    monthly_revenue: float
    monthly_total_cost: float
    monthly_profit: float
    break_even_units: float
    roi_monthly_pct: float
    payback_months: float
    is_profitable: bool


class AgentResult(TypedDict):
    score: int
    veredicto_corto: str
    analisis_extenso: str
    hallazgos_clave: list[str]
    recomendaciones: list[str]
    raw_calculations: Optional[dict]


class PipelineState(TypedDict):
    evaluation_id: str
    inputs: EvaluationInputs
    financial_result: Optional[AgentResult]
    market_result: Optional[AgentResult]
    risk_result: Optional[AgentResult]
    strategy_result: Optional[AgentResult]
    final_verdict: Optional[str]
    final_score: Optional[int]
    final_summary: Optional[str]
    error: Optional[str]
