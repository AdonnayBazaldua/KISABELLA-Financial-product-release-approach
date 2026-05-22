import json
from anthropic import Anthropic
from core.config import settings
from agents.schemas import EvaluationInputs, FinancialCalculations, AgentResult


def calculate_financials(inputs: EvaluationInputs) -> FinancialCalculations:
    units = max(inputs["estimated_units_month"], 1)
    price = inputs["target_price"]

    total_logistics = (
        inputs["cost_logistics_vehicle"]
        + inputs["cost_logistics_viaticos"]
        + inputs["cost_logistics_personnel"]
    )

    storage_per_unit = inputs["cost_storage"] / units
    marketing_per_unit = inputs["cost_marketing"] / units
    overhead_per_unit = inputs["cost_overhead"] / units

    shrinkage = inputs["cost_purchase"] * inputs["cost_shrinkage_pct"] / 100
    commission = price * inputs["cost_commission_pct"] / 100

    total_cost_per_unit = (
        inputs["cost_purchase"]
        + inputs["cost_freight"]
        + inputs["cost_customs"]
        + storage_per_unit
        + total_logistics
        + shrinkage
        + commission
        + marketing_per_unit
        + overhead_per_unit
    )

    acquisition_cost = inputs["cost_purchase"] + inputs["cost_freight"] + inputs["cost_customs"]
    gross_margin_pct = (price - acquisition_cost) / price * 100 if price > 0 else 0
    net_margin_pct = (price - total_cost_per_unit) / price * 100 if price > 0 else 0

    monthly_revenue = price * units
    monthly_total_cost = total_cost_per_unit * units
    monthly_profit = monthly_revenue - monthly_total_cost

    fixed_monthly = inputs["cost_storage"] + inputs["cost_marketing"] + inputs["cost_overhead"]
    variable_cost_per_unit = total_cost_per_unit - storage_per_unit - marketing_per_unit - overhead_per_unit
    contribution_margin = price - variable_cost_per_unit
    break_even_units = fixed_monthly / contribution_margin if contribution_margin > 0 else float("inf")

    initial_investment = inputs["cost_purchase"] * units
    roi_monthly_pct = (monthly_profit / initial_investment * 100) if initial_investment > 0 else 0

    payback_months = (initial_investment / monthly_profit) if monthly_profit > 0 else float("inf")

    return FinancialCalculations(
        total_logistics=round(total_logistics, 2),
        total_cost_per_unit=round(total_cost_per_unit, 2),
        gross_margin_pct=round(gross_margin_pct, 2),
        net_margin_pct=round(net_margin_pct, 2),
        monthly_revenue=round(monthly_revenue, 2),
        monthly_total_cost=round(monthly_total_cost, 2),
        monthly_profit=round(monthly_profit, 2),
        break_even_units=round(break_even_units, 0) if break_even_units != float("inf") else 9999,
        roi_monthly_pct=round(roi_monthly_pct, 2),
        payback_months=round(payback_months, 1) if payback_months != float("inf") else 99,
        is_profitable=monthly_profit > 0,
    )


def score_from_calculations(calcs: FinancialCalculations) -> int:
    score = 0

    # Margen neto (40 puntos)
    if calcs["net_margin_pct"] >= 30:
        score += 40
    elif calcs["net_margin_pct"] >= 20:
        score += 30
    elif calcs["net_margin_pct"] >= 10:
        score += 20
    elif calcs["net_margin_pct"] >= 5:
        score += 10

    # ROI mensual (30 puntos)
    if calcs["roi_monthly_pct"] >= 20:
        score += 30
    elif calcs["roi_monthly_pct"] >= 10:
        score += 20
    elif calcs["roi_monthly_pct"] >= 5:
        score += 10

    # Payback (20 puntos)
    if calcs["payback_months"] <= 3:
        score += 20
    elif calcs["payback_months"] <= 6:
        score += 15
    elif calcs["payback_months"] <= 12:
        score += 10

    # Rentabilidad binaria (10 puntos)
    if calcs["is_profitable"]:
        score += 10

    return min(score, 100)


def run_financial_agent(inputs: EvaluationInputs) -> AgentResult:
    calcs = calculate_financials(inputs)
    score = score_from_calculations(calcs)

    prompt = f"""Eres el Agente Financiero de CAPI kisabella, especialista en análisis de rentabilidad de productos físicos para el mercado mexicano.

Analiza la viabilidad financiera del siguiente producto y proporciona un análisis detallado en español.

**Producto:** {inputs['product_name']}
**Descripción:** {inputs['description']}
**Canal de venta:** {inputs['sales_channel']}
**Tipo de cambio usado:** ${inputs['exchange_rate']:.2f} MXN/USD

**Datos financieros calculados:**
- Costo total por unidad: ${calcs['total_cost_per_unit']:,.2f} MXN
- Precio de venta objetivo: ${inputs['target_price']:,.2f} MXN
- Margen bruto: {calcs['gross_margin_pct']:.1f}%
- Margen neto: {calcs['net_margin_pct']:.1f}%
- Unidades estimadas/mes: {inputs['estimated_units_month']}
- Ingreso mensual: ${calcs['monthly_revenue']:,.2f} MXN
- Utilidad mensual: ${calcs['monthly_profit']:,.2f} MXN
- Punto de equilibrio: {calcs['break_even_units']:.0f} unidades/mes
- ROI mensual: {calcs['roi_monthly_pct']:.1f}%
- Meses para recuperar inversión inicial: {calcs['payback_months']:.1f}

**Desglose de costos:**
- Costo de compra: ${inputs['cost_purchase']:,.2f} MXN
- Flete internacional: ${inputs['cost_freight']:,.2f} MXN
- Aranceles/aduanas: ${inputs['cost_customs']:,.2f} MXN
- Almacenamiento mensual: ${inputs['cost_storage']:,.2f} MXN
- Logística (vehículo + viáticos + personal): ${calcs['total_logistics']:,.2f} MXN
- Merma/devoluciones: {inputs['cost_shrinkage_pct']:.1f}%
- Comisión canal: {inputs['cost_commission_pct']:.1f}%
- Marketing mensual: ${inputs['cost_marketing']:,.2f} MXN
- Overhead prorrateado: ${inputs['cost_overhead']:,.2f} MXN

Proporciona tu respuesta en el siguiente formato JSON exacto (sin texto adicional fuera del JSON):

{{
  "veredicto_corto": "una frase de máximo 10 palabras sobre la viabilidad financiera",
  "analisis_extenso": "análisis completo de 300-500 palabras cubriendo: rentabilidad actual, riesgos financieros específicos, impacto del tipo de cambio, análisis del punto de equilibrio, y proyección a 6 meses",
  "hallazgos_clave": [
    "hallazgo financiero 1",
    "hallazgo financiero 2",
    "hallazgo financiero 3"
  ],
  "recomendaciones": [
    "recomendación accionable 1",
    "recomendación accionable 2",
    "recomendación accionable 3"
  ]
}}"""

    client = Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    content = message.content[0].text.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    parsed = json.loads(content)

    return AgentResult(
        score=score,
        veredicto_corto=parsed["veredicto_corto"],
        analisis_extenso=parsed["analisis_extenso"],
        hallazgos_clave=parsed["hallazgos_clave"],
        recomendaciones=parsed["recomendaciones"],
        raw_calculations=dict(calcs),
    )
