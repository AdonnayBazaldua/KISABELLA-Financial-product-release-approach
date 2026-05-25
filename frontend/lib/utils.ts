import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind classes resolviendo conflictos.
 * Patrón shadcn/ui estándar.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
