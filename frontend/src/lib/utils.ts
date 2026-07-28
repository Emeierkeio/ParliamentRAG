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

/** Debate titles from the resoconto ingest repeat the time marker, e.g.
 * "Svolgimento di interpellanze urgenti (ore 9,34). (ore 9,34) (ore 9,34)".
 * Keep the first occurrence of each "(ore …)" token and drop the echoes. */
export function cleanDebateTitle(title: string): string {
  const seen = new Set<string>();
  return title
    .replace(/\(ore\s+[\d.,:]+\)/gi, (m) => {
      const key = m.toLowerCase().replace(/\s+/g, "");
      if (seen.has(key)) return "";
      seen.add(key);
      return m;
    })
    .replace(/\s{2,}/g, " ")
    .replace(/\s+\./g, ".")
    .replace(/\.{2,}$/, ".")
    .trim();
}
