/**
 * Alias estables sobre los tipos generados desde el OpenAPI del backend (ADR-0004).
 * NO definir tipos HTTP a mano aqui: cambia el schema Pydantic y corre
 * `npm run gen:types` (la guarda `npm run check:types` falla si hay deriva).
 */
import type { components } from "./types.generated";

type S = components["schemas"];

export type EvaluationStatus = S["EvaluationDetail"]["status"];
export type Verdict = NonNullable<S["EvaluationDetail"]["final_verdict"]>;
export type AgentStatus = S["AgentResultDTO"]["status"];
export type AgentName = "financiero" | "mercado" | "riesgo" | "estrategia";

export type AgentResultDTO = S["AgentResultDTO"];
export type EvaluationSummary = S["EvaluationSummary"];
export type EvaluationDetail = S["EvaluationDetail"];
export type EvaluationCreated = S["EvaluationCreated"];
export type CreateEvaluationPayload = S["CreateEvaluationRequest"];
