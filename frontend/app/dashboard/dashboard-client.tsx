"use client";

import { useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { CompareBar } from "@/components/compare-bar";
import type { EvaluationSummary, Verdict } from "@/lib/types";
import { VERDICT_COLORS, VERDICT_LABELS } from "@/lib/verdicts";

function verdictBadge(verdict: Verdict | null) {
  if (verdict === null) return null;
  return (
    <Badge className={VERDICT_COLORS[verdict]}>{VERDICT_LABELS[verdict]}</Badge>
  );
}

export function DashboardClient({
  evaluations,
}: {
  evaluations: EvaluationSummary[];
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < 3) {
        next.add(id);
      }
      return next;
    });
  }

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
          <p className="text-lg mb-4">No hay evaluaciones aun</p>
          <Link
            href="/evaluations/new"
            className="text-slate-700 underline hover:text-slate-900"
          >
            Crear la primera evaluacion
          </Link>
        </div>
      ) : (
        <div className="space-y-3 pb-20">
          {evaluations.map((ev) => {
            const isComplete = ev.status === "complete";
            const isSelected = selected.has(ev.id);

            return (
              <div key={ev.id} className="flex items-center gap-3">
                {isComplete && (
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleSelect(ev.id)}
                    disabled={!isSelected && selected.size >= 3}
                    className="w-4 h-4 rounded border-slate-300 text-slate-700 focus:ring-slate-500 shrink-0"
                  />
                )}
                {!isComplete && <div className="w-4 shrink-0" />}
                <Link href={`/evaluations/${ev.id}`} className="flex-1">
                  <Card className="p-5 hover:border-slate-400 hover:shadow-sm transition-all flex items-center justify-between">
                    <div>
                      <h2 className="font-semibold text-slate-900">{ev.name}</h2>
                      <p className="text-sm text-slate-500">{ev.product_name}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      {ev.final_score !== null && (
                        <span className="text-lg font-bold text-slate-700">
                          {ev.final_score}
                        </span>
                      )}
                      {verdictBadge(ev.final_verdict as Verdict | null)}
                      {ev.status === "error" && (
                        <Badge className="bg-red-50 text-red-700 border-red-200">Error</Badge>
                      )}
                      {!isComplete && ev.status !== "error" && (
                        <Badge className="bg-slate-100 text-slate-600 border-slate-200">En proceso</Badge>
                      )}
                    </div>
                  </Card>
                </Link>
              </div>
            );
          })}
        </div>
      )}

      <CompareBar
        selectedIds={Array.from(selected)}
        onClear={() => setSelected(new Set())}
      />
    </div>
  );
}
