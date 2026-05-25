/**
 * Types HTTP — espejo de api/v1/schemas.py en el backend.
 *
 * TODO Sprint 1+: reemplazar este archivo manual por codegen desde
 * /openapi.json con `npm run gen:types` (script en package.json).
 * Mientras tanto, mantener sincronizado a mano.
 */

export type EvaluationStatus =
  | "pending"
  | "queued"
  | "running"
  | "complete"
  | "error";

export type Verdict = "viable" | "viable_con_ajustes" | "no_viable";

export type AgentStatus =
  | "pending"
  | "running"
  | "ok"
  | "failed"
  | "degraded";

export type AgentName = "financiero" | "mercado" | "riesgo" | "estrategia";

export interface AgentResultDTO {
  agent_name: string;
  status: AgentStatus;
  score: number | null;
  veredicto_corto: string | null;
  analisis_extenso: string | null;
  hallazgos_clave: string[];
  recomendaciones: string[];
  error_message?: string | null;
}

export interface EvaluationSummary {
  id: string;
  name: string;
  product_name: string;
  status: EvaluationStatus;
  final_verdict: Verdict | null;
  final_score: number | null;
  created_at: string;
}

export interface EvaluationDetail {
  id: string;
  name: string;
  product_name: string;
  status: EvaluationStatus;
  final_verdict: Verdict | null;
  final_score: number | null;
  final_summary: string | null;
  error_message: string | null;
  warn_flags: string[];
  requires_human_review: boolean;
  progress: Record<string, AgentStatus>;
  agent_results: AgentResultDTO[];
  created_at: string;
  updated_at: string;
}

export interface EvaluationCreated {
  evaluation_id: string;
  status: "pending";
}

export interface CreateEvaluationPayload {
  name: string;
  product_name: string;
  description?: string | null;
  category?: "fisico" | "servicio";
  sales_channel?: string | null;
  cost_purchase: number | string;
  cost_purchase_usd?: number | string | null;
  cost_freight?: number | string;
  cost_customs?: number | string;
  cost_storage?: number | string;
  cost_logistics_vehicle?: number | string;
  cost_logistics_viaticos?: number | string;
  cost_logistics_personnel?: number | string;
  cost_shrinkage_pct?: number | string;
  cost_commission_pct?: number | string;
  cost_marketing?: number | string;
  cost_overhead?: number | string;
  target_price: number | string;
  estimated_units_month: number;
  exchange_rate_used: number | string;
}
