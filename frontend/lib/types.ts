export type EvaluationStatus = "pending" | "running" | "complete" | "error";
export type Verdict = "viable" | "viable_con_ajustes" | "no_viable";

export interface AgentResult {
  agent_name: string;
  score: number;
  veredicto_corto: string;
  analisis_extenso: string;
  hallazgos_clave: string[];
  recomendaciones: string[];
  raw_calculations: Record<string, number> | null;
}

export interface EvaluationSummary {
  id: string;
  name: string;
  status: EvaluationStatus;
  final_verdict: Verdict | null;
  final_score: number | null;
  created_at: string;
}

export interface EvaluationDetail extends EvaluationSummary {
  final_summary: string | null;
  inputs: {
    product_name: string;
    target_price: number;
    exchange_rate_used: number | null;
  } | null;
  agent_results: AgentResult[];
}

export interface CreateEvaluationPayload {
  name: string;
  product_name: string;
  description: string;
  category: string;
  cost_purchase: number;
  cost_purchase_usd: number;
  cost_freight: number;
  cost_customs: number;
  cost_storage: number;
  cost_logistics_vehicle: number;
  cost_logistics_viaticos: number;
  cost_logistics_personnel: number;
  cost_shrinkage_pct: number;
  cost_commission_pct: number;
  cost_marketing: number;
  cost_overhead: number;
  target_price: number;
  estimated_units_month: number;
  sales_channel: string;
  exchange_rate_used: number;
}
