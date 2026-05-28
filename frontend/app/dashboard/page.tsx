import { api } from "@/lib/api";
import type { EvaluationSummary } from "@/lib/types";
import { DashboardClient } from "./dashboard-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

async function getEvaluations(): Promise<EvaluationSummary[]> {
  try {
    return await api.listEvaluations();
  } catch {
    return [];
  }
}

export default async function DashboardPage() {
  const evaluations = await getEvaluations();
  return <DashboardClient evaluations={evaluations} />;
}
