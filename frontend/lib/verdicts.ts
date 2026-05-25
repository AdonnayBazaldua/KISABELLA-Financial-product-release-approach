import type { Verdict } from "./types";

/**
 * Configuración central de veredictos.
 * NO duplicar este mapping en componentes — siempre importar de aquí.
 */

export const VERDICT_LABELS: Record<Verdict, string> = {
  viable: "Viable",
  viable_con_ajustes: "Con ajustes",
  no_viable: "No viable",
};

export const VERDICT_COLORS: Record<Verdict, string> = {
  viable: "bg-emerald-100 text-emerald-800 border-emerald-200",
  viable_con_ajustes: "bg-amber-100 text-amber-800 border-amber-200",
  no_viable: "bg-rose-100 text-rose-800 border-rose-200",
};

export const VERDICT_ICONS: Record<Verdict, string> = {
  viable: "✓",
  viable_con_ajustes: "⚠",
  no_viable: "✗",
};

/**
 * Status del pipeline (transitorios + finales).
 */
export const STATUS_LABELS: Record<string, string> = {
  pending: "Pendiente",
  queued: "En cola",
  running: "Analizando",
  complete: "Completo",
  error: "Error",
};

export const AGENT_LABELS: Record<string, string> = {
  financiero: "Financiero",
  mercado: "Mercado",
  riesgo: "Riesgo",
  estrategia: "Estrategia",
};
