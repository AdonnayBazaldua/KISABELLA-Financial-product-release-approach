import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { Scorecard } from "@/components/scorecard";
import Link from "next/link";

export default async function EvaluationPage({ params }: { params: { id: string } }) {
  let evaluation;
  try {
    evaluation = await api.getEvaluation(params.id);
  } catch {
    notFound();
  }

  return (
    <div>
      <div className="max-w-3xl mx-auto px-4 pt-4">
        <Link href="/dashboard" className="text-sm text-slate-500 hover:text-slate-800">
          ← Volver al dashboard
        </Link>
      </div>
      <Scorecard evaluation={evaluation} />
    </div>
  );
}
