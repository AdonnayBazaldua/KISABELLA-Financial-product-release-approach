import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { EvaluationSummary, Verdict } from "@/lib/types";
import { VERDICT_COLORS, VERDICT_LABELS } from "@/lib/verdicts";

// Audit P0-6: sin esto, el dashboard cachea entre invocaciones SSR
// y nunca refleja nuevas evaluaciones hasta restart del server.
export const dynamic = "force-dynamic";
export const revalidate = 0;

async function getEvaluations(): Promise<EvaluationSummary[]> {
  try {
    return await api.listEvaluations();
  } catch {
    // TODO Sprint 6: distinguir error de red vs 4xx/5xx para mostrar mensaje útil
    return [];
  }
}

function verdictBadge(verdict: Verdict | null) {
  if (verdict === null) return null;
  return (
    <Badge className={VERDICT_COLORS[verdict]}>{VERDICT_LABELS[verdict]}</Badge>
  );
}

export default async function DashboardPage() {
  const evaluations = await getEvaluations();

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Evaluaciones</h1>
        <span className="text-sm text-slate-500">
          {evaluations.length} total
        </span>
      </div>

      {evaluations.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <p className="text-lg mb-4">No hay evaluaciones aún</p>
          <Link
            href="/evaluations/new"
            className="text-slate-700 underline hover:text-slate-900"
          >
            Crear la primera evaluación
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {evaluations.map((ev) => (
            <Link key={ev.id} href={`/evaluations/${ev.id}`}>
              <Card className="p-5 hover:border-slate-400 hover:shadow-sm transition-all flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-slate-900">{ev.name}</h2>
                  <p className="text-sm text-slate-500 mt-0.5">
                    {new Date(ev.created_at).toLocaleDateString("es-MX", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {ev.final_score !== null && (
                    <span className="text-xl font-bold text-slate-900">
                      {ev.final_score}
                    </span>
                  )}
                  {verdictBadge(ev.final_verdict)}
                  {(ev.status === "running" || ev.status === "queued") && (
                    <Badge variant="info">Analizando...</Badge>
                  )}
                  {ev.status === "error" && (
                    <Badge variant="destructive">Error</Badge>
                  )}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
