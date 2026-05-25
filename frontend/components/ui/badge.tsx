import * as React from "react";
import { cn } from "@/lib/utils";

type Variant =
  | "default"
  | "success"
  | "warning"
  | "destructive"
  | "info"
  | "neutral";

const VARIANTS: Record<Variant, string> = {
  default: "bg-slate-100 text-slate-800 border-slate-200",
  success: "bg-emerald-100 text-emerald-800 border-emerald-200",
  warning: "bg-amber-100 text-amber-800 border-amber-200",
  destructive: "bg-rose-100 text-rose-800 border-rose-200",
  info: "bg-blue-100 text-blue-800 border-blue-200",
  neutral: "bg-slate-50 text-slate-600 border-slate-200",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

export function Badge({
  className,
  variant = "default",
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center text-xs font-semibold px-2 py-1 rounded-full border",
        VARIANTS[variant],
        className
      )}
      {...props}
    />
  );
}
