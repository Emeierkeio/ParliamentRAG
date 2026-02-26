import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Convert ISO date string (YYYY-MM-DD) to Italian display format (DD/MM/YYYY). */
export function formatDate(d: string): string {
  return d.split('-').reverse().join('/');
}

/** Convert a string to Title Case (first letter uppercase, rest lowercase per word). */
export function toTitleCase(s: string): string {
  return s.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
}
