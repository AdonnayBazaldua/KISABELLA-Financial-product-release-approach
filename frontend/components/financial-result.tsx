"use client";
import { useState } from "react";
import { EvaluationDetail, AgentResultDTO, Verdict } from "@/lib/types";
import { ChevronDown, ChevronRight, TrendingUp, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

const VERDICT_CONFIG: Record<Verdict, { label: string; bgColor: string; borderColor: string; icon: React.ReactNode }> = {
  viable: {
    label: "Viable",
    bgColor: "bg-green-50",
    borderColor: "border-green-300",
    icon: <CheckCircle2 className="text-green-600" size={32} />,
  },
  viable_con_ajustes: {
    label: "Viable con ajustes",
    bgColor: "bg-yellow-50",
    borderColor: "border-yellow-300",
    icon: <AlertTriangle className="text-yellow-600" size={32} />,
  },
  no_viable: {
    label: "No viable",
    bgColor: "bg-red-50",
    borderColor: "border-red-300",
    icon: <XCircle className="text-red-600" size={32} />,
  },
};

const AGENT_LABELS: Record<string, string> = {
  financiero: "Agente Financiero",
  mercado: "Agente de Mercado",
  riesgo: "Agente de Riesgo",
  estrategia: "Agente de Estrategia Comercial",
  orquestador: "Orquestador",
};

function ScoreBar({ value }: { value: number }) {
  return (
    <div className="w-24 h-2 bg-slate-200 rounded-full overflow-hidden">
      <div
        className="h-full bg-slate-700 rounded-full transition-all"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

function AgentCard({ result }: { result: AgentResultDTO }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border rounded-lg mb-4 bg-white">
      <div className="p-4">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-base font-semibold text-slate-700">
            {AGENT_LABELS[result.agent_name] ?? result.agent_name}
          </h3>
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-slate-900">{result.score ?? "—"}/100</span>
            <ScoreBar value={result.score ?? 0} />
          </div>
        </div>
        <p className="text-sm text-slate-500 italic">{result.veredicto_corto}</p>
      </div>
      <div className="px-4 pb-4">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 transition-colors mb-3"
        >
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {open ? "Ocultar análisis" : "Ver análisis completo"}
        </button>
        {open && (
          <div className="space-y-4">
            <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
              {result.analisis_extenso}
            </p>
            {result.hallazgos_clave.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold uppercase text-slate-500 mb-2 tracking-wide">Hallazgos clave</h4>
                <ul className="space-y-1">
                  {result.hallazgos_clave.map((h, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                      <TrendingUp size={14} className="mt-0.5 text-blue-500 shrink-0" />
                      {h}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {result.recomendaciones.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold uppercase text-slate-500 mb-2 tracking-wide">Recomendaciones</h4>
                <ul className="space-y-1">
                  {result.recomendaciones.map((r, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                      <CheckCircle2 size={14} className="mt-0.5 text-green-500 shrink-0" />
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function FinancialResult({ evaluation }: { evaluation: EvaluationDetail }) {
  const verdict = evaluation.final_verdict as Verdict | null;
  const config = verdict ? VERDICT_CONFIG[verdict] : null;

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold text-slate-900 mb-2">{evaluation.name}</h1>
      <p className="text-sm text-slate-500 mb-6">
        {evaluation.product_name}
      </p>

      {config && verdict && (
        <div className={`flex items-center gap-4 p-6 border-2 rounded-xl mb-6 ${config.bgColor} ${config.borderColor}`}>
          <div>{config.icon}</div>
          <div className="flex-1">
            <span className={`inline-block text-sm font-semibold px-3 py-1 rounded-full border ${config.borderColor} ${config.bgColor}`}>
              {config.label}
            </span>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {evaluation.final_score}
              <span className="text-lg text-slate-400">/100</span>
            </p>
          </div>
          <ScoreBar value={evaluation.final_score ?? 0} />
        </div>
      )}

      <h2 className="text-lg font-semibold text-slate-800 mb-4">Análisis por agente</h2>
      {evaluation.agent_results.map((result) => (
        <AgentCard key={result.agent_name} result={result} />
      ))}
    </div>
  );
}
