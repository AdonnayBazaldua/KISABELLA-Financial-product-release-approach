"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { CreateEvaluationPayload } from "@/lib/types";
import { CostSection, CostField } from "./cost-section";
import { RefreshCw, Loader2 } from "lucide-react";

const EMPTY_FORM: CreateEvaluationPayload = {
  name: "",
  product_name: "",
  description: "",
  category: "fisico",
  cost_purchase: 0,
  cost_purchase_usd: 0,
  cost_freight: 0,
  cost_customs: 0,
  cost_storage: 0,
  cost_logistics_vehicle: 0,
  cost_logistics_viaticos: 0,
  cost_logistics_personnel: 0,
  cost_shrinkage_pct: 0,
  cost_commission_pct: 0,
  cost_marketing: 0,
  cost_overhead: 0,
  target_price: 0,
  estimated_units_month: 1,
  sales_channel: "",
  exchange_rate_used: 19.5,
};

export function EvaluationForm() {
  const router = useRouter();
  const [form, setForm] = useState<CreateEvaluationPayload>(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [tcLoading, setTcLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTC();
  }, []);

  async function fetchTC() {
    setTcLoading(true);
    try {
      const data = await api.getExchangeRate();
      setForm((f) => ({ ...f, exchange_rate_used: data.rate }));
    } finally {
      setTcLoading(false);
    }
  }

  function handleChange(name: string, value: number | string) {
    setForm((f) => ({ ...f, [name]: value }));
  }

  function handleUSD(value: number) {
    setForm((f) => ({
      ...f,
      cost_purchase_usd: value,
      cost_purchase: parseFloat((value * Number(f.exchange_rate_used)).toFixed(2)),
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await api.createEvaluation(form);
      router.push(`/evaluations/${result.evaluation_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-3xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Nueva Evaluación</h1>

      <CostSection title="1. Producto" defaultOpen>
        <div className="col-span-2">
          <CostField label="Nombre de la evaluación" name="name" value={form.name} onChange={handleChange} type="text" required />
        </div>
        <div className="col-span-2">
          <CostField label="Nombre del producto" name="product_name" value={form.product_name} onChange={handleChange} type="text" required />
        </div>
        <div className="col-span-2">
          <label htmlFor="description" className="text-sm font-medium text-slate-600">Descripción</label>
          <textarea
            id="description"
            name="description"
            value={form.description ?? ""}
            onChange={(e) => handleChange("description", e.target.value)}
            rows={3}
            className="w-full border rounded-md px-3 py-2 text-sm mt-1 focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
        </div>
        <CostField label="Canal de venta" name="sales_channel" value={form.sales_channel ?? ""} onChange={handleChange} type="text" />
      </CostSection>

      <CostSection title="2. Estructura de Costos">
        <div className="col-span-2 flex items-center gap-3 p-3 bg-slate-50 rounded-lg mb-2">
          <span className="text-sm font-medium text-slate-600">TC USD/MXN:</span>
          <span className="font-bold text-slate-900">${Number(form.exchange_rate_used).toFixed(4)}</span>
          <button type="button" onClick={fetchTC} className="text-slate-500 hover:text-slate-800">
            {tcLoading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </button>
        </div>
        <CostField label="Costo de compra (USD)" name="cost_purchase_usd" value={form.cost_purchase_usd ?? 0} onChange={(_, v) => handleUSD(v as number)} suffix="USD" />
        <CostField label="Costo de compra (MXN)" name="cost_purchase" value={form.cost_purchase} onChange={handleChange} suffix="MXN" />
        <CostField label="Flete internacional" name="cost_freight" value={form.cost_freight ?? 0} onChange={handleChange} suffix="MXN" />
        <CostField label="Aranceles / Importación" name="cost_customs" value={form.cost_customs ?? 0} onChange={handleChange} suffix="MXN" />
        <CostField label="Almacenamiento mensual" name="cost_storage" value={form.cost_storage ?? 0} onChange={handleChange} suffix="MXN/mes" />
        <CostField label="Logística — Vehículo" name="cost_logistics_vehicle" value={form.cost_logistics_vehicle ?? 0} onChange={handleChange} suffix="MXN" />
        <CostField label="Logística — Viáticos" name="cost_logistics_viaticos" value={form.cost_logistics_viaticos ?? 0} onChange={handleChange} suffix="MXN" />
        <CostField label="Logística — Personal" name="cost_logistics_personnel" value={form.cost_logistics_personnel ?? 0} onChange={handleChange} suffix="MXN" />
        <CostField label="Merma / Devoluciones" name="cost_shrinkage_pct" value={form.cost_shrinkage_pct ?? 0} onChange={handleChange} suffix="%" />
        <CostField label="Comisión vendedor / canal" name="cost_commission_pct" value={form.cost_commission_pct ?? 0} onChange={handleChange} suffix="%" />
        <CostField label="Marketing mensual" name="cost_marketing" value={form.cost_marketing ?? 0} onChange={handleChange} suffix="MXN/mes" />
        <CostField label="Overhead prorrateado" name="cost_overhead" value={form.cost_overhead ?? 0} onChange={handleChange} suffix="MXN/mes" />
      </CostSection>

      <CostSection title="3. Precio y Volumen">
        <CostField label="Precio objetivo de venta" name="target_price" value={form.target_price} onChange={handleChange} suffix="MXN" min={0.01} required />
        <CostField label="Unidades estimadas / mes" name="estimated_units_month" value={form.estimated_units_month} onChange={handleChange} step="1" min={1} required />
      </CostSection>

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg p-4 mb-4 text-sm">{error}</div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full h-12 text-base font-semibold bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
      >
        {loading ? (
          <><Loader2 size={18} className="animate-spin" /> Analizando...</>
        ) : (
          "Analizar"
        )}
      </button>
    </form>
  );
}
