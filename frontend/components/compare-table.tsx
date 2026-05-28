"use client";

import * as Progress from "@radix-ui/react-progress";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { EvaluationDetail, Verdict } from "@/lib/types";
import { VERDICT_COLORS, VERDICT_LABELS } from "@/lib/verdicts";

const AGENT_LABELS: Record<string, string> = {
  financiero: "Financiero",
  mercado: "Mercado",
  riesgo: "Riesgo",
  estrategia: "Estrategia",
};

function MiniGauge({ score }: { score: number }) {
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color =
    score >= 75
      ? "stroke-emerald-500"
      : score >= 50
        ? "stroke-amber-500"
        : "stroke-rose-500";

  return (
    <div className="relative w-14 h-14">
      <svg viewBox="0 0 50 50" className="w-full h-full -rotate-90">
        <circle cx="25" cy="25" r={radius} fill="none" strokeWidth="4" className="text-slate-100" stroke="currentColor" />
        <circle cx="25" cy="25" r={radius} fill="none" strokeWidth="4" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} className={`${color} transition-all`} />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xs font-bold text-slate-900">{score}</span>
      </div>
    </div>
  );
}

function ScoreRow({ label, scores }: { label: string; scores: (number | null)[] }) {
  return (
    <tr className="border-b border-slate-100">
      <td className="py-2 pr-4 text-xs font-medium text-slate-600 whitespace-nowrap">{label}</td>
      {scores.map((score, i) => (
        <td key={i} className="py-2 px-3">
          {score !== null ? (
            <div className="flex items-center gap-2">
              <Progress.Root value={score} max={100} className="h-2 flex-1 bg-slate-100 rounded-full overflow-hidden">
                <Progress.Indicator
                  className={`h-full rounded-full ${score >= 75 ? "bg-emerald-500" : score >= 50 ? "bg-amber-500" : "bg-rose-500"}`}
                  style={{ width: `${score}%` }}
                />
              </Progress.Root>
              <span className="text-xs font-medium text-slate-700 w-7 text-right">{score}</span>
            </div>
          ) : (
            <span className="text-xs text-slate-400">-</span>
          )}
        </td>
      ))}
    </tr>
  );
}

export function CompareTable({ evaluations }: { evaluations: EvaluationDetail[] }) {
  const agentNames = ["financiero", "mercado", "riesgo", "estrategia"];

  return (
    <Card>
      <CardContent className="p-0 overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="py-3 px-4 text-left text-xs font-semibold text-slate-500 w-28"></th>
              {evaluations.map((ev) => (
                <th key={ev.id} className="py-3 px-3 text-left min-w-[180px]">
                  <p className="text-sm font-semibold text-slate-900 truncate">{ev.name}</p>
                  <p className="text-xs text-slate-500 truncate">{ev.product_name}</p>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-slate-100">
              <td className="py-3 px-4 text-xs font-medium text-slate-600">Veredicto</td>
              {evaluations.map((ev) => {
                const verdict = ev.final_verdict as Verdict | null;
                return (
                  <td key={ev.id} className="py-3 px-3">
                    <div className="flex items-center gap-3">
                      <MiniGauge score={ev.final_score ?? 0} />
                      {verdict && (
                        <Badge className={VERDICT_COLORS[verdict]}>
                          {VERDICT_LABELS[verdict]}
                        </Badge>
                      )}
                    </div>
                  </td>
                );
              })}
            </tr>
            {agentNames.map((agent) => (
              <ScoreRow
                key={agent}
                label={AGENT_LABELS[agent] ?? agent}
                scores={evaluations.map((ev) => {
                  const r = ev.agent_results.find((a) => a.agent_name === agent);
                  return r?.score ?? null;
                })}
              />
            ))}
            <tr className="border-b border-slate-100">
              <td className="py-2 px-4 text-xs font-medium text-slate-600">Alertas</td>
              {evaluations.map((ev) => (
                <td key={ev.id} className="py-2 px-3">
                  {ev.warn_flags.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {ev.warn_flags.map((f) => (
                        <Badge key={f} variant="warning">{f}</Badge>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400">Sin alertas</span>
                  )}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-2 px-4 text-xs font-medium text-slate-600">Fecha</td>
              {evaluations.map((ev) => (
                <td key={ev.id} className="py-2 px-3 text-xs text-slate-500">
                  {new Date(ev.created_at).toLocaleDateString("es-MX")}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
