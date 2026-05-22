const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API error ${res.status}: ${error}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getExchangeRate: () =>
    apiFetch<{ rate: number; source: string }>("/api/exchange-rate"),

  createEvaluation: (payload: import("./types").CreateEvaluationPayload) =>
    apiFetch<{ evaluation_id: string }>("/api/evaluations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listEvaluations: () =>
    apiFetch<import("./types").EvaluationSummary[]>("/api/evaluations"),

  getEvaluation: (id: string) =>
    apiFetch<import("./types").EvaluationDetail>(`/api/evaluations/${id}`),
};
