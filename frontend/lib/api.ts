/**
 * Cliente HTTP del backend FastAPI.
 *
 * URL split:
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

/** Mensaje legible de un error del backend. Los 422 de FastAPI traen una lista por campo. */
export function errorDetail(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e: { loc?: unknown[]; msg?: string }) => `${e.loc?.at(-1) ?? "campo"}: ${e.msg}`)
      .join("; ");
  }
  if (typeof detail === "string") return detail;
  const nested = (detail as { detail?: unknown } | undefined)?.detail;
  return typeof nested === "string" ? nested : `HTTP ${status}`;
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
      detail = errorDetail(await res.json(), res.status);
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
   * TC USD/MXN — conectado a Banxico con cache en backend.
   * El form usa este valor como sugerencia editable.
   */
  getExchangeRate: () =>
    apiFetch<{ rate: number; source: string; date: string }>("/api/v1/tc"),

  compareEvaluations: (ids: string[]) =>
    apiFetch<EvaluationDetail[]>(
      `/api/v1/evaluations/compare?ids=${ids.join(",")}`
    ),
};
