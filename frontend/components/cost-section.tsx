"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface Props {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

export function CostSection({ title, children, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border rounded-lg mb-4">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left font-semibold text-slate-800 hover:bg-slate-50 transition-colors"
      >
        <span>{title}</span>
        {open ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
      </button>
      {open && <div className="p-4 pt-0 grid grid-cols-2 gap-4">{children}</div>}
    </div>
  );
}

interface FieldProps {
  label: string;
  name: string;
  value: number | string;
  onChange: (name: string, value: number | string) => void;
  type?: "number" | "text";
  suffix?: string;
  step?: string;
  min?: number;
  required?: boolean;
}

export function CostField({ label, name, value, onChange, type = "number", suffix, step = "0.01", min = 0, required }: FieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={name} className="text-sm font-medium text-slate-600">{label}</label>
      <div className="relative flex items-center">
        <input
          id={name}
          required={required}
          type={type}
          name={name}
          value={value}
          step={step}
          min={type === "number" ? min : undefined}
          onChange={(e) => onChange(name, type === "number" ? parseFloat(e.target.value) || 0 : e.target.value)}
          className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
        />
        {suffix && (
          <span className="absolute right-3 text-xs text-slate-400">{suffix}</span>
        )}
      </div>
    </div>
  );
}
