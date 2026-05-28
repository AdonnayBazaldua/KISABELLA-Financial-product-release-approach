/**
 * Cliente HTTP del backend FastAPI.
 *
 * URL split (audit P0-7):
 * - Server Components corren en el contenedor → usan API_URL_INTERNAL
 *   (red Docker interna: http://backend:8000).
 * - Browser/Client Components → usan NEXT_PUBLIC_API_URL (dominio público).
 *
 * typeof window === "undefined" detecta server-side.
 */

import type {
  CreateEvaluationPayload,
  EvaluationCreated,
  EvaluationDetail,
  EvaluationSummary,
} from "./types";

const PUBLIC_API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const INTERNAL_API_URL =
  process.env.API_URL_INTERNAL ?? PUBLIC_API_URL;

function getBaseUrl(): string {
  // Server-side fetch: dentro del contenedor
  if (typeof window === "undefined") return INTERNAL_API_URL;
  return PUBLIC_API_URL;
}

interface FetchOptions extends RequestInit {
  /** Cache strategy. Default 'no-store' para data fresca. */
  cache?: RequestCache;
}

async function apiFetch<T>(
  path: string,
  options?: FetchOptions
): Promise<T> {
  const base = getBaseUrl();
  const res = await fetch(`${base}${path}`, {
    cache: options?.cache ?? "no-store",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail?.detail ?? body?.detail ?? JSON.stringify(body);
    } catch {
      detail = await res.text().catch(() => detail);
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export const api = {
  createEvaluation: (payload: CreateEvaluationPayload) =>
    apiFetch<EvaluationCreated>("/api/v1/evaluations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listEvaluations: () =>
    apiFetch<EvaluationSummary[]>("/api/v1/evaluations"),

  getEvaluation: (id: string) =>
    apiFetch<EvaluationDetail>(`/api/v1/evaluations/${id}`),

  /**
   * TC USD/MXN — Sprint 6 conecta Banxico real.
   * Por ahora retorna fallback estable; el backend tampoco lo persiste
   * desde Banxico aún. El form usa este valor como sugerencia editable.
   */
  getExchangeRate: async (): Promise<{ rate: number; source: string }> => {
    // TODO Sprint 6: GET /api/v1/exchange-rate (Banxico con cache)
    return { rate: 19.85, source: "fallback" };
  },

  compareEvaluations: (ids: string[]) =>
    apiFetch<EvaluationDetail[]>(
      `/api/v1/evaluations/compare?ids=${ids.join(",")}`
    ),
};
