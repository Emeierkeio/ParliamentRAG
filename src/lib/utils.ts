import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Convert ISO date string (YYYY-MM-DD) to Italian display format (DD/MM/YYYY). */
export function formatDate(d: string): string {
  return d.split('-').reverse().join('/');
}
