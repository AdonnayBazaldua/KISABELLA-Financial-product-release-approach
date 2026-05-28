"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function CompareBar({
  selectedIds,
  onClear,
}: {
  selectedIds: string[];
  onClear: () => void;
}) {
  const router = useRouter();
  const count = selectedIds.length;
  const canCompare = count >= 2 && count <= 3;

  if (count === 0) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 shadow-lg z-50">
      <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
        <span className="text-sm text-slate-600">
          {count} evaluacion{count > 1 ? "es" : ""} seleccionada{count > 1 ? "s" : ""}
          {count === 1 && " — selecciona al menos 2"}
        </span>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={onClear}>
            Limpiar
          </Button>
          <Button
            size="sm"
            disabled={!canCompare}
            onClick={() => router.push(`/evaluations/compare?ids=${selectedIds.join(",")}`)}
          >
            Comparar
          </Button>
        </div>
      </div>
    </div>
  );
}
