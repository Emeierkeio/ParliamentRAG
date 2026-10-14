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
import { SOLO_BASE } from "./solo-base";
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
type Camera = keyof Stats["by_chamber"];
type CampoCamera = keyof Stats["by_chamber"]["camera"];
const S: Stats = { ...base.stats };
for (const k of Object.keys(S) as (keyof Stats)[]) {
  const v = (fotografia as Record<string, unknown>)[k];
  if (v !== null && v !== undefined && k !== "fonte" && !SOLO_BASE.includes(k)) (S as Record<string, unknown>)[k] = v;
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

/*
 * Camera e Senato restano separati: ogni numero che ha una camera si legge
 * per camera, mai sommato. Temi EuroVoc e triple sono comuni ai due rami.
 */
const CAMERE: Record<Lingua, [Camera, string, string][]> = {
  it: [
    ["camera", "Camera dei Deputati", "Camera"],
    ["senato", "Senato della Repubblica", "Senato"],
  ],
  en: [
    ["camera", "Chamber of Deputies", "Chamber"],
    ["senato", "Senate of the Republic", "Senate"],
  ],
};

const PER_CAMERA: Record<Lingua, [CampoCamera, string | Record<Camera, string>][]> = {
  it: [
    ["speeches", "interventi in Aula, con testo integrale"],
    ["individual_votes", "voti individuali, uno per parlamentare e votazione"],
    ["acts", "atti parlamentari"],
    ["votes", "votazioni elettroniche"],
    ["sessions", "sedute"],
    ["people", { camera: "deputati della legislatura, subentrati compresi", senato: "senatori della legislatura, subentrati compresi" }],
  ],
  en: [
    ["speeches", "speeches on the floor, with the full text"],
    ["individual_votes", "individual votes, one per member and vote"],
    ["acts", "parliamentary acts"],
    ["votes", "electronic votes"],
    ["sessions", "sittings"],
    ["people", { camera: "deputies in this legislature, replacements included", senato: "senators in this legislature, replacements included" }],
  ],
};

const COMUNI: Record<Lingua, ["eurovoc_concepts" | "triples", string][]> = {
  it: [
    ["eurovoc_concepts", "temi EuroVoc collegati agli atti, comuni ai due rami"],
    ["triples", "triple RDF nell'export"],
  ],
  en: [
    ["eurovoc_concepts", "EuroVoc topics linked to the acts, shared by both houses"],
    ["triples", "RDF triples in the export"],
  ],
};

const PERSONE: Record<Lingua, string> = {
  it: "parlamentari della legislatura, subentrati compresi",
  en: "members of Parliament in this legislature, replacements included",
};
const voce = (t: string | Record<Camera, string>, c: Camera) => (typeof t === "string" ? t : t[c]);

/*
 * Chi c'è dietro il numero dei parlamentari: in carica, usciti durante la
 * legislatura, senatori a vita, Governo senza seggio. I numeri sono span con
 * data-c/data-k, che gli script delle pagine aggiornano con i valori vivi.
 */
function chi(l: Lingua): string {
  const n = (k: string, c?: Camera) => {
    const v = c ? (S.by_chamber[c] as Record<string, number>)[k] : (S as Record<string, unknown>)[k];
    return `<span${c ? ` data-c="${c}"` : ""} data-k="${k}">${numero(v as number, l)}</span>`;
  };
  const napolitano = S.by_chamber.senato.life_senators_former === 1;
  return l === "en"
    ? `<b>Who they are.</b> In the Chamber, ${n("people_in_office", "camera")} deputies in office and ${n("people_former", "camera")} who left during the legislature. ` +
        `In the Senate, ${n("people_in_office", "senato")} senators in office, ${n("life_senators_in_office", "senato")} of them for life, and ${n("people_former", "senato")} no longer in office` +
        (napolitano ? ", including Giorgio Napolitano, senator for life, who died in 2023" : "") +
        `. The graph also has ${n("government_without_seat")} members of the Government without a seat in Parliament.`
    : `<b>Chi sono.</b> Alla Camera ${n("people_in_office", "camera")} deputati in carica e ${n("people_former", "camera")} che hanno lasciato durante la legislatura. ` +
        `Al Senato ${n("people_in_office", "senato")} senatori in carica, di cui ${n("life_senators_in_office", "senato")} a vita, e ${n("people_former", "senato")} non più in carica` +
        (napolitano ? ", tra cui il senatore a vita Giorgio Napolitano, scomparso nel 2023" : "") +
        `. Nel grafo ci sono anche ${n("government_without_seat")} membri del Governo senza seggio in Parlamento.`;
}

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
    numeri:
      '<div class="camere">' +
      CAMERE[l]
        .map(
          ([c, nome], j) =>
            `<div class="camere__ramo compare" style="--ritardo:${j * 120}ms"><h3 class="camere__nome">${nome}</h3><div class="camere__cifre">` +
            PER_CAMERA[l]
              .map(
                ([k, t]) =>
                  `<div class="cifra"><p class="cifra__n" data-c="${c}" data-k="${k}">${numero(S.by_chamber[c][k], l)}</p><p class="cifra__l">${voce(t, c)}</p></div>`,
              )
              .join("") +
            "</div></div>",
        )
        .join("") +
      `</div><p class="camere__chi compare">${chi(l)}</p><div class="numeri__comuni">` +
      COMUNI[l]
        .map(
          ([k, t], i) =>
            `<div class="cifra compare" style="--ritardo:${i * 80}ms"><p class="cifra__n" data-k="${k}">${numero(S[k], l)}</p><p class="cifra__l">${t}</p></div>`,
        )
        .join("") +
      "</div>",
  };
}

function dati(l: Lingua): Record<string, string> {
  const riga = (t: string, v: string) => `<div><dt>${t}</dt><dd>${v}</dd></div>`;
  const agg = `<span data-data-agg>${data(S.last_update, l)}</span>`;
  const onto = '<span class="mono">w3id.org/parliamentrag/ontology#</span>';
  return {
    frontespizio:
      l === "en"
        ? riga("Coverage", "Chamber of Deputies and Senate of the Republic, 19th legislature") +
          riga("Format", "RDF Turtle, plus tables on Hugging Face") +
          riga("Sources", "dati.camera.it, dati.senato.it, EuroVoc") +
          riga("Licence", "CC BY-SA 4.0") +
          riga("Updated", agg) +
          riga("Ontology", onto)
        : riga("Copertura", "Camera dei Deputati e Senato della Repubblica, XIX legislatura") +
          riga("Formato", "RDF Turtle, più tabelle su Hugging Face") +
          riga("Fonti", "dati.camera.it, dati.senato.it, EuroVoc") +
          riga("Licenza", "CC BY-SA 4.0") +
          riga("Aggiornato", agg) +
          riga("Ontologia", onto),
    dataAgg: data(S.last_update, l),
    registro:
      '<div class="registro registro--camere">' +
      `<div class="registro__riga registro__testa"><span class="registro__l"></span>${CAMERE[l].map(([, , breve]) => `<span class="registro__ramo">${breve}</span>`).join("")}</div>` +
      PER_CAMERA[l]
        .map(
          ([k, t], i) =>
            `<div class="registro__riga compare" style="--ritardo:${(i % 2) * 80}ms"><span class="registro__l">${typeof t === "string" ? t : PERSONE[l]}</span>` +
            CAMERE[l]
              .map(([c]) => `<span class="registro__n" data-c="${c}" data-k="${k}">${numero(S.by_chamber[c][k], l)}</span>`)
              .join("") +
            "</div>",
        )
        .join("") +
      `</div><p class="registro__chi compare">${chi(l)}</p><div class="registro registro--comuni">` +
      COMUNI[l]
        .map(
          ([k, t], i) =>
            `<div class="registro__riga compare" style="--ritardo:${(i % 2) * 80}ms"><span class="registro__l">${t}</span><span class="registro__n" data-k="${k}">${numero(S[k], l)}</span></div>`,
        )
        .join("") +
      "</div>",
    triple: numero(S.triples, l),
  };
}

export function riempi(html: string, pagina: "home" | "dati", l: Lingua): string {
  const valori = pagina === "home" ? home(l) : dati(l);
  return html.replace(/\{\{(\w+)\}\}/g, (tutto, nome: string) => valori[nome] ?? tutto);
}
