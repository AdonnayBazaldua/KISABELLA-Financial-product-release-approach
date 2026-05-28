import { redirect } from "next/navigation";
import { api } from "@/lib/api";
import { CompareTable } from "@/components/compare-table";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function ComparePage({
  searchParams,
}: {
  searchParams: { ids?: string };
}) {
  const idsParam = searchParams.ids;
  if (!idsParam) redirect("/dashboard");

  const ids = idsParam.split(",").filter(Boolean);
  if (ids.length < 2 || ids.length > 3) redirect("/dashboard");

  let evaluations;
  try {
    evaluations = await api.compareEvaluations(ids);
  } catch {
    redirect("/dashboard");
  }

  return (
    <div className="max-w-5xl mx-auto py-8 px-4">
      <div className="mb-6">
        <Link href="/dashboard" className="text-sm text-slate-500 hover:text-slate-800">
          ← Volver al dashboard
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 mt-2">
          Comparativa de evaluaciones
        </h1>
        <p className="text-sm text-slate-500">
          {evaluations.length} evaluaciones seleccionadas
        </p>
      </div>
      <CompareTable evaluations={evaluations} />
    </div>
  );
}
