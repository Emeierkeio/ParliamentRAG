/*
 * Le pagine del sito e i loro indirizzi. L'italiano sta alla radice, l'inglese
 * sotto /en con slug inglesi. Ogni pagina ha la sua coppia: serve al cambio di
 * lingua nella testata, agli hreflang e alla sitemap.
 */

export type Lingua = "it" | "en";

export type IdPagina =
  | "home"
  | "metodo"
  | "verifica"
  | "dati"
  | "ricerca"
  | "sviluppatori"
  | "aggiornamenti"
  | "privacy"
  | "termini"
  | "confermata";

export const SITO = (process.env.PUBLIC_SITE_URL || "https://www.parliamentrag.it").replace(/\/$/, "");

export const PERCORSI: Record<IdPagina, Record<Lingua, string>> = {
  home: { it: "/", en: "/en" },
  metodo: { it: "/metodo", en: "/en/method" },
  verifica: { it: "/verifica", en: "/en/verification" },
  dati: { it: "/dati", en: "/en/data" },
  ricerca: { it: "/ricerca", en: "/en/research" },
  sviluppatori: { it: "/sviluppatori", en: "/en/developers" },
  aggiornamenti: { it: "/aggiornamenti", en: "/en/updates" },
  privacy: { it: "/privacy", en: "/en/privacy" },
  termini: { it: "/termini", en: "/en/terms" },
  confermata: { it: "/newsletter/confirmed", en: "/en/newsletter/confirmed" },
};

/** Pagine che finiscono nella sitemap (la conferma della newsletter no). */
export const IN_SITEMAP: IdPagina[] = [
  "home",
  "metodo",
  "verifica",
  "dati",
  "ricerca",
  "sviluppatori",
  "aggiornamenti",
  "privacy",
  "termini",
];

export function percorso(id: IdPagina, lingua: Lingua): string {
  return PERCORSI[id][lingua];
}

/* Voci del menu, nell'ordine della testata */
export const NAV: { id: IdPagina; it: string; en: string }[] = [
  { id: "metodo", it: "Metodo", en: "Method" },
  { id: "verifica", it: "Verifica", en: "Verification" },
  { id: "dati", it: "Dati", en: "Data" },
  { id: "ricerca", it: "Ricerca", en: "Research" },
  { id: "sviluppatori", it: "Sviluppatori", en: "Developers" },
  { id: "aggiornamenti", it: "Aggiornamenti", en: "Updates" },
];

export const SISTEMI = {
  stenografo: "https://www.stenografo.it",
  fascicoli: "https://www.fascicoli.it",
  scranno: "https://www.scranno.it",
};
