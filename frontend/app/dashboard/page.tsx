import Link from "next/link";
import { api } from "@/lib/api";
import { EvaluationSummary, Verdict } from "@/lib/types";

const VERDICT_LABELS: Record<Verdict, string> = {
  viable: "Viable",
  viable_con_ajustes: "Con ajustes",
  no_viable: "No viable",
};

const VERDICT_COLORS: Record<Verdict, string> = {
  viable: "bg-green-100 text-green-800",
  viable_con_ajustes: "bg-yellow-100 text-yellow-800",
  no_viable: "bg-red-100 text-red-800",
};

async function getEvaluations(): Promise<EvaluationSummary[]> {
  try {
    return await api.listEvaluations();
  } catch {
    return [];
  }
}

export default async function DashboardPage() {
  const evaluations = await getEvaluations();

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Evaluaciones</h1>
        <span className="text-sm text-slate-500">{evaluations.length} total</span>
      </div>

      {evaluations.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <p className="text-lg mb-4">No hay evaluaciones aún</p>
          <Link href="/evaluations/new" className="text-slate-600 underline">
            Crear la primera evaluación
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {evaluations.map((ev) => (
            <Link key={ev.id} href={`/evaluations/${ev.id}`}>
              <div className="bg-white border border-slate-200 rounded-xl p-5 hover:border-slate-400 hover:shadow-sm transition-all flex items-center justify-between">
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
                    <span className="text-xl font-bold text-slate-900">{ev.final_score}</span>
                  )}
                  {ev.final_verdict && (
                    <span className={`text-xs font-semibold px-2 py-1 rounded-full ${VERDICT_COLORS[ev.final_verdict]}`}>
                      {VERDICT_LABELS[ev.final_verdict]}
                    </span>
                  )}
                  {ev.status === "running" && (
                    <span className="text-xs font-semibold px-2 py-1 rounded-full bg-blue-100 text-blue-800">
                      Analizando...
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
