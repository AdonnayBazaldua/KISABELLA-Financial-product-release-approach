"use client";

import { useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import * as Progress from "@radix-ui/react-progress";
import {
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";
import { warnFlagLabel } from "@/lib/verdicts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  EvaluationDetail,
  AgentResultDTO,
  Verdict,
  AgentStatus,
} from "@/lib/types";

const VERDICT_CONFIG: Record<
  Verdict,
  { label: string; variant: "success" | "warning" | "destructive"; icon: React.ReactNode }
> = {
  viable: {
    label: "Viable",
    variant: "success",
    icon: <CheckCircle2 className="w-5 h-5" />,
  },
  viable_con_ajustes: {
    label: "Viable con ajustes",
    variant: "warning",
    icon: <AlertTriangle className="w-5 h-5" />,
  },
  no_viable: {
    label: "No viable",
    variant: "destructive",
    icon: <XCircle className="w-5 h-5" />,
  },
};

const AGENT_LABELS: Record<string, string> = {
  financiero: "Financiero",
  mercado: "Mercado",
  riesgo: "Riesgo",
  estrategia: "Estrategia",
};

const STATUS_CONFIG: Record<AgentStatus, { color: string; label: string }> = {
  ok: { color: "text-emerald-600", label: "OK" },
  failed: { color: "text-rose-600", label: "Error" },
  degraded: { color: "text-amber-600", label: "Degradado" },
  running: { color: "text-blue-600", label: "Ejecutando..." },
  pending: { color: "text-slate-400", label: "Pendiente" },
};

function ScoreGauge({ score }: { score: number }) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color =
    score >= 75
      ? "stroke-emerald-500"
      : score >= 50
        ? "stroke-amber-500"
        : "stroke-rose-500";

  return (
    <div className="relative w-28 h-28">
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          className="text-slate-100"
        />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={`${color} transition-all duration-700`}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-2xl font-bold text-slate-900">{score}</span>
      </div>
    </div>
  );
}

function WarnBanner({
  flags,
  requiresReview,
}: {
  flags: string[];
  requiresReview: boolean;
}) {
  if (flags.length === 0 && !requiresReview) return null;

  return (
    <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg mb-6">
      <ShieldAlert className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
      <div>
        {requiresReview && (
          <p className="text-sm font-medium text-amber-800">
            Esta evaluacion requiere revision humana.
          </p>
        )}
        {flags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-1">
            {flags.map((flag) => (
              <Badge key={flag} variant="warning">
                {warnFlagLabel(flag)}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AgentCard({ result }: { result: AgentResultDTO }) {
  const [open, setOpen] = useState(false);
  const label = AGENT_LABELS[result.agent_name] ?? result.agent_name;
  const statusCfg = STATUS_CONFIG[result.status] ?? STATUS_CONFIG.pending;
  const score = result.score ?? 0;

  return (
    <Card className="mb-3">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">{label}</CardTitle>
          <span className={`text-xs font-medium ${statusCfg.color}`}>
            {statusCfg.label}
          </span>
        </div>
        {result.status === "ok" && (
          <div className="mt-2">
            <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
              <span>Score</span>
              <span className="font-medium text-slate-700">{score}/100</span>
            </div>
            <Progress.Root
              value={score}
              max={100}
              className="h-2 bg-slate-100 rounded-full overflow-hidden"
            >
              <Progress.Indicator
                className={`h-full rounded-full transition-all duration-500 ${
                  score >= 75
                    ? "bg-emerald-500"
                    : score >= 50
                      ? "bg-amber-500"
                      : "bg-rose-500"
                }`}
                style={{ width: `${score}%` }}
              />
            </Progress.Root>
          </div>
        )}
        {result.veredicto_corto && (
          <p className="text-xs text-slate-600 mt-2">{result.veredicto_corto}</p>
        )}
      </CardHeader>

      {result.status === "ok" && (result.hallazgos_clave.length > 0 || result.recomendaciones.length > 0) && (
        <Collapsible.Root open={open} onOpenChange={setOpen}>
          <Collapsible.Trigger className="flex items-center gap-1 px-5 py-2 text-xs text-slate-500 hover:text-slate-700 w-full">
            {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            Ver detalle
          </Collapsible.Trigger>
          <Collapsible.Content>
            <CardContent className="pt-0">
              {result.hallazgos_clave.length > 0 && (
                <div className="mb-3">
                  <h4 className="text-xs font-semibold text-slate-700 mb-1">Hallazgos</h4>
                  <ul className="text-xs text-slate-600 space-y-1">
                    {result.hallazgos_clave.map((h, i) => (
                      <li key={i} className="flex gap-1.5">
                        <span className="text-slate-400">-</span>
                        {h}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {result.recomendaciones.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-700 mb-1">Recomendaciones</h4>
                  <ul className="text-xs text-slate-600 space-y-1">
                    {result.recomendaciones.map((r, i) => (
                      <li key={i} className="flex gap-1.5">
                        <span className="text-emerald-500">{"→"}</span>
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Collapsible.Content>
        </Collapsible.Root>
      )}

      {result.status === "failed" && result.error_message && (
        <CardContent className="pt-0">
          <p className="text-xs text-rose-600">{result.error_message}</p>
        </CardContent>
      )}
    </Card>
  );
}

function LoadingSkeleton() {
  return (
    <div className="max-w-3xl mx-auto py-8 px-4 animate-pulse">
      <div className="h-8 bg-slate-200 rounded w-64 mb-2" />
      <div className="h-4 bg-slate-100 rounded w-40 mb-6" />
      <div className="h-32 bg-slate-100 rounded-xl mb-6" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 bg-slate-100 rounded-xl" />
        ))}
      </div>
    </div>
  );
}

export function Scorecard({ evaluation }: { evaluation: EvaluationDetail }) {
  if (evaluation.status === "pending" || evaluation.status === "running" || evaluation.status === "queued") {
    return <LoadingSkeleton />;
  }

  const verdict = evaluation.final_verdict as Verdict | null;
  const config = verdict ? VERDICT_CONFIG[verdict] : null;

  if (evaluation.status === "error") {
    return (
      <div className="max-w-3xl mx-auto py-8 px-4">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">{evaluation.name}</h1>
        <div className="flex items-start gap-3 p-4 bg-rose-50 border border-rose-200 rounded-lg">
          <XCircle className="w-5 h-5 text-rose-600 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-rose-800">Error en la evaluacion</p>
            <p className="text-sm text-rose-600 mt-1">{evaluation.error_message}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">{evaluation.name}</h1>
      <p className="text-sm text-slate-500 mb-6">{evaluation.product_name}</p>

      {config && verdict && (
        <div className="flex items-center gap-6 p-6 border rounded-xl mb-6 bg-white">
          <ScoreGauge score={evaluation.final_score ?? 0} />
          <div className="flex-1">
            <Badge variant={config.variant} className="mb-2">
              {config.icon}
              <span className="ml-1.5">{config.label}</span>
            </Badge>
            <p className="text-sm text-slate-600">
              Score compuesto: <span className="font-semibold">{evaluation.final_score}/100</span>
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Confianza: {evaluation.requires_human_review ? "baja" : "alta"}
            </p>
          </div>
        </div>
      )}

      <WarnBanner
        flags={evaluation.warn_flags}
        requiresReview={evaluation.requires_human_review}
      />

      <h2 className="text-base font-semibold text-slate-800 mb-3 flex items-center gap-2">
        <TrendingUp className="w-4 h-4" />
        Analisis por agente
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        {evaluation.agent_results.map((result) => (
          <AgentCard key={result.agent_name} result={result} />
        ))}
      </div>

      {evaluation.final_summary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Justificacion del veredicto</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-700 whitespace-pre-line leading-relaxed">
              {evaluation.final_summary}
            </p>
          </CardContent>
        </Card>
      )}

      {evaluation.tokens_input != null && (
        <p className="text-xs text-slate-400 mt-4 text-right">
          Consumo del modelo: {evaluation.tokens_input.toLocaleString("es-MX")} tokens de entrada ·{" "}
          {(evaluation.tokens_output ?? 0).toLocaleString("es-MX")} de salida
        </p>
      )}
    </div>
  );
}
