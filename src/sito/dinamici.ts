/*
 * Parti delle pagine che dipendono dai dati, scritte già nell'HTML al build:
 * la pagina nasce completa, senza spazi vuoti che si riempiono dopo e senza
 * spostamenti. Gli script in public/sito/pagine/ aggiungono il comportamento
 * e aggiornano numeri e date con i valori vivi di /sito/dati.js.
 *
 * Nei frammenti delle pagine i segnaposto sono «{{nome}}».
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import base from "./dati-base.json";
import fotografia from "../data/site-data.json";
import { esc } from "./guscio";
import type { Lingua } from "./rotte";

type Citazione = (typeof base.tema.citazioni)[number];

const SPUNTA =
  '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.2 8.2l1.9 1.9 3.8-4"/></svg>';

/* Stesso ordine e stesse etichette di public/sito/pagine/home.js */
const ORDINE = ["FdI", "PD", "Lega", "M5S", "FI", "AVS", "Azione", "IV", "NM", "+Europa", "Governo"];
const BREVE: Record<string, string> = {
  FdI: "Fratelli d'Italia", PD: "Partito Democratico", Lega: "Lega", M5S: "Movimento 5 Stelle", FI: "Forza Italia",
  AVS: "Alleanza Verdi e Sinistra", Azione: "Azione", IV: "Italia Viva", NM: "Noi Moderati", "+Europa": "+Europa", Governo: "Governo",
};
const GRUPPI_AULA: { k: string; seggi: string | null; componente?: string }[] = [
  { k: "AVS", seggi: "AVS" }, { k: "M5S", seggi: "M5S" }, { k: "PD", seggi: "PD" }, { k: "Azione", seggi: "Azione" },
  { k: "IV", seggi: "IV" }, { k: "+Europa", seggi: "Misto", componente: "+Europa" }, { k: "NM", seggi: "NM" },
  { k: "FI", seggi: "FI" }, { k: "Lega", seggi: "Lega" }, { k: "FdI", seggi: "FdI" }, { k: "Governo", seggi: null },
];

const etichetta = (g: string, l: Lingua) => (l === "en" && g === "Governo" ? "Government" : g);
const perGruppo: Record<string, Citazione> = Object.fromEntries(base.tema.citazioni.map((q) => [q.group, q]));

function data(s: string, l: Lingua): string {
  const [a, m, g] = s.split("-").map(Number);
  return new Date(Date.UTC(a, m - 1, g)).toLocaleDateString(l === "en" ? "en-GB" : "it-IT", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}
function numero(n: number, l: Lingua): string {
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, l === "en" ? "," : ".");
}

/* Numeri del grafo al build: la fotografia notturna (scripts/snapshot-data.mjs) */
type Stats = typeof base.stats;
const S: Stats = { ...base.stats };
for (const k of Object.keys(S) as (keyof Stats)[]) {
  const v = (fotografia as Record<string, unknown>)[k];
  if (v !== null && v !== undefined && k !== "fonte") (S as Record<string, unknown>)[k] = v;
}

/* Seggi dell'Aula da public/sito/aula.js (window.AULA=…) */
/* k: tipo di seggio (d deputato, g Governo, …); c: componente del Misto */
type Seggio = { x: number; y: number; k: string; g?: string; c?: string };
function seggi(): Seggio[] {
  try {
    const testo = readFileSync(join(process.cwd(), "public/sito/aula.js"), "utf8");
    return JSON.parse(testo.slice(testo.indexOf("{"), testo.lastIndexOf("}") + 1)).seats;
  } catch {
    return [];
  }
}

const CIFRE: Record<Lingua, [keyof Stats, string][]> = {
  it: [
    ["speeches", "interventi in Aula, con testo integrale"],
    ["individual_votes", "voti individuali, uno per deputato"],
    ["acts", "atti parlamentari"],
    ["votes", "votazioni elettroniche"],
    ["sessions", "sedute"],
    ["people", "deputati e membri del Governo"],
    ["eurovoc_concepts", "temi EuroVoc collegati agli atti"],
    ["triples", "triple RDF nell'export"],
  ],
  en: [
    ["speeches", "speeches in the Chamber, with full text"],
    ["individual_votes", "individual votes, one per deputy"],
    ["acts", "parliamentary acts"],
    ["votes", "electronic votes"],
    ["sessions", "sittings"],
    ["people", "deputies and members of the Government"],
    ["eurovoc_concepts", "EuroVoc topics linked to the acts"],
    ["triples", "RDF triples in the export"],
  ],
};

const REGISTRO: Record<Lingua, string[]> = {
  it: [
    "interventi in Aula, con il testo integrale",
    "voti individuali, uno per deputato e votazione",
    "atti parlamentari",
    "votazioni elettroniche",
    "sedute",
    "deputati e membri del Governo",
    "temi EuroVoc collegati agli atti",
    "triple RDF nell'export",
  ],
  en: [
    "speeches in the Chamber, with the full text",
    "individual votes, one per deputy and vote",
    "parliamentary acts",
    "electronic votes",
    "sittings",
    "deputies and members of the Government",
    "EuroVoc topics linked to the acts",
    "RDF triples in the export",
  ],
};

function home(l: Lingua): Record<string, string> {
  const verbale = l === "en" ? "Official record" : "Verbale ufficiale";
  const mostra = l === "en" ? "Show the quote from " : "Mostra la citazione di ";
  const tutti = seggi();
  const conta: Record<string, number> = {};
  for (const s of tutti) {
    if (s.g) conta[s.g] = (conta[s.g] ?? 0) + 1;
    if (s.c) conta["c:" + s.c] = (conta["c:" + s.c] ?? 0) + 1;
  }
  return {
    sigle: ORDINE.map(
      (g, i) =>
        `<button type="button" class="sigla" aria-pressed="${i === 0}" data-i="${i}" title="${esc(mostra + etichetta(g, l))}">${esc(etichetta(g, l))}</button>`,
    ).join(""),
    voci: ORDINE.map((g, i) => {
      const q = perGruppo[g];
      const breve = l === "en" && g === "Governo" ? "Government" : BREVE[g];
      return (
        `<blockquote class="cit cit--piccola"${i === 0 ? " data-on" : ""}><p class="cit__testo" lang="it">${esc(q.quote)}</p>` +
        `<footer class="cit__fonte"><span class="cit__chi">${esc(q.name)}</span><span>${esc(breve)}</span><span>${data(q.date, l)}</span>` +
        `<a class="bollino" href="${esc(q.url)}" rel="noopener">${SPUNTA}${verbale}</a></footer></blockquote>`
      );
    }).join(""),
    // Stato iniziale della prova dell'Aula: PD scelto, come fa home.js
    seggi: tutti
      .map(
        (s) =>
          `<circle cx="${s.x}" cy="${s.y}" r="17" data-g="${s.g ?? ""}" data-k="${s.k}"${s.c ? ` data-c="${esc(s.c)}"` : ""}${s.g === "PD" ? " data-on" : ""}></circle>`,
      )
      .join(""),
    voce: (() => {
      const q = perGruppo.PD;
      return (
        `<blockquote class="cit cit--piccola" style="margin-top:var(--s-3)"><p class="cit__testo" lang="it">${esc(q.quote)}</p>` +
        `<footer class="cit__fonte"><span class="cit__chi">${esc(q.name)}</span><span>${esc(q.groupName)}</span><span>${data(q.date, l)}</span>` +
        `<a class="bollino" href="${esc(q.url)}" rel="noopener">${SPUNTA}${verbale}</a></footer></blockquote>`
      );
    })(),
    // Confronto parola per parola: la citazione intatta coincide
    parole: perGruppo.FdI.quote
      .split(/\s+/)
      .map((w) => `<span data-s="ok" data-fin="ok">${esc(w)}</span>`)
      .join(" "),
    esito:
      SPUNTA +
      (l === "en"
        ? "<strong>It matches the record.</strong> <span>The quote stays, with the link to sitting 510.</span>"
        : "<strong>Coincide con il resoconto.</strong> <span>La citazione resta, con il link alla seduta 510.</span>"),
    gruppi: GRUPPI_AULA.map((g) => {
      const n = g.componente ? conta["c:" + g.componente] : g.seggi ? conta[g.seggi] : null;
      return (
        `<button type="button" aria-pressed="${g.k === "PD"}" data-k="${esc(g.k)}">${SPUNTA}<span>${esc(etichetta(g.k, l))}</span>` +
        `<span class="n">${n ?? "—"}</span></button>`
      );
    }).join(""),
    dataAgg: data(S.last_update, l),
    numeri: CIFRE[l]
      .map(
        ([k, t], i) =>
          `<div class="cifra compare" style="--ritardo:${(i % 4) * 80}ms"><p class="cifra__n" data-k="${k}">${numero(S[k] as number, l)}</p><p class="cifra__l">${t}</p></div>`,
      )
      .join(""),
  };
}

function dati(l: Lingua): Record<string, string> {
  const riga = (t: string, v: string) => `<div><dt>${t}</dt><dd>${v}</dd></div>`;
  const agg = `<span data-data-agg>${data(S.last_update, l)}</span>`;
  const onto = '<span class="mono">w3id.org/parliamentrag/ontology#</span>';
  const chiavi: (keyof Stats)[] = ["speeches", "individual_votes", "acts", "votes", "sessions", "people", "eurovoc_concepts", "triples"];
  return {
    frontespizio:
      l === "en"
        ? riga("Coverage", "Chamber of Deputies, 19th legislature") +
          riga("Format", "RDF Turtle, plus tables on Hugging Face") +
          riga("Sources", "dati.camera.it, EuroVoc") +
          riga("Licence", "CC BY-SA 4.0") +
          riga("Updated", agg) +
          riga("Ontology", onto)
        : riga("Copertura", "Camera dei Deputati, XIX legislatura") +
          riga("Formato", "RDF Turtle, più tabelle su Hugging Face") +
          riga("Fonti", "dati.camera.it, EuroVoc") +
          riga("Licenza", "CC BY-SA 4.0") +
          riga("Aggiornato", agg) +
          riga("Ontologia", onto),
    dataAgg: data(S.last_update, l),
    registro: chiavi
      .map(
        (k, i) =>
          `<div class="registro__riga compare" style="--ritardo:${(i % 2) * 80}ms"><span class="registro__l">${REGISTRO[l][i]}</span><span class="registro__n" data-k="${k}">${numero(S[k] as number, l)}</span></div>`,
      )
      .join(""),
    triple: numero(S.triples, l),
  };
}

export function riempi(html: string, pagina: "home" | "dati", l: Lingua): string {
  const valori = pagina === "home" ? home(l) : dati(l);
  return html.replace(/\{\{(\w+)\}\}/g, (tutto, nome: string) => valori[nome] ?? tutto);
}
