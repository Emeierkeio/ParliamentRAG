/*
 * Il guscio di ogni pagina: <head> con titolo, descrizione, canonical,
 * hreflang e Open Graph; testata, piede e script. È HTML scritto qui, non
 * React: le pagine sono documenti statici con piccoli script (public/sito),
 * come nel prototipo del design system «Resoconto». Nessuna idratazione,
 * quindi gli script possono toccare il DOM liberamente.
 */
import { NAV, PERCORSI, SISTEMI, SITO, percorso, type IdPagina, type Lingua } from "./rotte";

export type Contenuto = {
  /** <title> completo */
  titolo: string;
  descrizione: string;
  /** Il contenuto di <main> */
  html: string;
};

export type Opzioni = {
  id: IdPagina | null;
  lingua: Lingua;
  contenuto: Contenuto;
  /** Foglio di stile della pagina in public/sito/pagine/, senza estensione */
  css?: string;
  /** Script della pagina in public/sito/, nell'ordine di caricamento */
  script?: string[];
  /** Voce di menu da segnare come corrente */
  voce?: IdPagina;
  /** Pagina da non indicizzare (404, conferma newsletter) */
  noindex?: boolean;
};

/* Cambia a ogni deploy: forza il browser a riprendere CSS e JS aggiornati */
const VERSIONE = (process.env.RAILWAY_GIT_COMMIT_SHA || Date.now().toString(36)).slice(0, 8);
const NOINDEX = process.env.NOINDEX === "1";

export function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

function v(src: string): string {
  return `${src}?v=${VERSIONE}`;
}

/* Stessi tracciati di public/sito/famiglia.js (window.MARCHI) */
export function marchioParliamentrag(anima: boolean): string {
  return (
    '<svg viewBox="15 15 194 153" aria-hidden="true" focusable="false">' +
    `<path ${anima ? 'class="penna" pathLength="1" ' : ""}d="M 35.91 139.73 A 81 81 0 1 1 188.09 139.73" fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round"/>` +
    `<circle ${anima ? 'class="penna-punto" ' : ""}cx="112" cy="146" r="22" fill="#2D5F8F"/></svg>`
  );
}

const MENU =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M4 8h16M4 16h16"/></svg>';

const T = {
  it: {
    salta: "Vai al contenuto",
    home: "ParliamentRAG, pagina iniziale",
    sezioni: "Sezioni",
    lingua: "Lingua",
    altra: "English version",
    tema: "Cambia tema",
    menu: "Apri il menu",
    piedeChi: "Progetto di ricerca per l'AI sui dibattiti delle istituzioni italiane. Università di Milano-Bicocca.",
    piedeNota: "Progetto indipendente: non è affiliato alla Camera dei Deputati e non parla a suo nome.",
    sistemi: "Sistemi",
    progetto: "Progetto",
    legali: "Note legali",
    datiAperti: "Dati aperti",
    licenza: "Licenza dei dati CC BY-SA 4.0",
    licenzaUrl: "https://creativecommons.org/licenses/by-sa/4.0/deed.it",
    sostegno: "Con il sostegno del programma EU Horizon Europe, grant",
    ogLocale: "it_IT",
    ogAlt: "it_IT",
  },
  en: {
    salta: "Skip to content",
    home: "ParliamentRAG, home page",
    sezioni: "Sections",
    lingua: "Language",
    altra: "Versione italiana",
    tema: "Change theme",
    menu: "Open the menu",
    piedeChi: "Research project on AI for the debates of Italian institutions. University of Milano-Bicocca.",
    piedeNota: "Independent project: it is not affiliated with the Chamber of Deputies and does not speak on its behalf.",
    sistemi: "Systems",
    progetto: "Project",
    legali: "Legal",
    datiAperti: "Open data",
    licenza: "Data licence CC BY-SA 4.0",
    licenzaUrl: "https://creativecommons.org/licenses/by-sa/4.0/deed.en",
    sostegno: "Supported by the EU Horizon Europe programme, grant",
    ogLocale: "en_GB",
    ogAlt: "en_GB",
  },
} as const;

/* Le voci della barra della lingua: la corrente è un testo, l'altra un link */
function lingue(id: IdPagina | null, lingua: Lingua): string {
  const t = T[lingua];
  const altra: Lingua = lingua === "it" ? "en" : "it";
  const href = id ? PERCORSI[id][altra] : PERCORSI.home[altra];
  const voce = (l: Lingua) =>
    l === lingua
      ? `<span aria-current="true" class="lingua__ora">${l.toUpperCase()}</span>`
      : `<a href="${href}" hreflang="${l}" lang="${l}" aria-label="${t.altra}">${l.toUpperCase()}</a>`;
  return `<div class="lingua" role="group" aria-label="${t.lingua}">${voce("it")}${voce("en")}</div>`;
}

function testata(o: Opzioni): string {
  const t = T[o.lingua];
  const nav = NAV.map(
    (n) =>
      `<a href="${percorso(n.id, o.lingua)}"${n.id === o.voce ? ' aria-current="page"' : ""}>${n[o.lingua]}</a>`,
  ).join("");
  return (
    '<header class="sito" data-testata><div class="pagina sito__in">' +
    `<a class="marchio" href="${percorso("home", o.lingua)}" aria-label="${t.home}">${marchioParliamentrag(false)}<span class="marchio__nome">ParliamentRAG</span></a>` +
    `<nav class="nav" id="nav" aria-label="${t.sezioni}">${nav}</nav>` +
    '<div class="sito__azioni">' +
    lingue(o.id, o.lingua) +
    `<button class="btn btn--linea btn--icona" type="button" data-tema aria-label="${t.tema}"></button>` +
    `<button class="btn btn--linea btn--icona menu-btn" type="button" aria-controls="nav" aria-expanded="false" aria-label="${t.menu}">${MENU}</button>` +
    "</div></div></header>"
  );
}

function piede(lingua: Lingua): string {
  const t = T[lingua];
  const p = (id: IdPagina) => percorso(id, lingua);
  const vociProgetto: [IdPagina, string][] =
    lingua === "it"
      ? [["metodo", "Metodo"], ["verifica", "Verifica"], ["dati", t.datiAperti], ["ricerca", "Ricerca"], ["sviluppatori", "Sviluppatori"], ["aggiornamenti", "Aggiornamenti"]]
      : [["metodo", "Method"], ["verifica", "Verification"], ["dati", t.datiAperti], ["ricerca", "Research"], ["sviluppatori", "Developers"], ["aggiornamenti", "Updates"]];
  return (
    '<footer class="piede" data-piede><div class="pagina">' +
    '<div class="piede__griglia">' +
    '<div class="pila" style="--pila:var(--s-4)">' +
    `<a class="marchio" href="${p("home")}">${marchioParliamentrag(false)}<span class="marchio__nome">ParliamentRAG</span></a>` +
    `<p style="max-width:40ch">${esc(t.piedeChi)}</p>` +
    `<p class="nota">${esc(t.piedeNota)}</p>` +
    "</div>" +
    `<div><h2>${t.sistemi}</h2><ul>` +
    `<li><a href="${SISTEMI.stenografo}">Stenografo</a></li>` +
    `<li><a href="${SISTEMI.fascicoli}">Fascicoli</a></li>` +
    `<li><a href="${SISTEMI.scranno}">Scranno</a></li>` +
    "</ul></div>" +
    `<div><h2>${t.progetto}</h2><ul>` +
    vociProgetto.map(([id, nome]) => `<li><a href="${p(id)}">${nome}</a></li>`).join("") +
    "</ul></div>" +
    `<div><h2>${t.legali}</h2><ul>` +
    `<li><a href="${p("privacy")}">Privacy</a></li>` +
    `<li><a href="${p("termini")}">${lingua === "it" ? "Termini" : "Terms"}</a></li>` +
    `<li><a href="${t.licenzaUrl}" rel="noopener">${t.licenza}</a></li>` +
    '<li><a href="https://dati.camera.it/" rel="noopener">dati.camera.it</a></li>' +
    '<li><a href="mailto:contatti@parliamentrag.it">contatti@parliamentrag.it</a></li>' +
    "</ul></div>" +
    "</div>" +
    '<div class="piede__fondo">' +
    `<p>${t.sostegno} <a href="https://doi.org/10.3030/101189771" rel="noopener">101189771</a> (<a href="https://datapact.eu/" rel="noopener">DataPACT</a>)</p>` +
    '<p>Mirko Tritella · <a href="https://emeierkeio.github.io" rel="noopener">emeierkeio.github.io</a></p>' +
    "</div></div></footer>"
  );
}

/* iOS: immagini di avvio per l'app aggiunta alla schermata Home (scripts/generate_splash.py) */
const SPLASH: [number, number, number][] = [
  [440, 956, 3], [430, 932, 3], [428, 926, 3], [420, 912, 3], [414, 896, 3], [414, 896, 2],
  [402, 874, 3], [393, 852, 3], [390, 844, 3], [375, 812, 3], [375, 667, 2],
];
const AVVIO = SPLASH.flatMap(([w, h, d]) =>
  (["light", "dark"] as const).map(
    (s) =>
      `<link rel="apple-touch-startup-image" href="/splash/apple-splash-${w * d}x${h * d}-${s}.png" media="(device-width: ${w}px) and (device-height: ${h}px) and (-webkit-device-pixel-ratio: ${d}) and (orientation: portrait) and (prefers-color-scheme: ${s})">`,
  ),
).join("");

/* Prima che la pagina si disegni: tema salvato (niente lampo chiaro→scuro). */
const SUBITO =
  "(function(){var r=document.documentElement;r.classList.remove('no-js');" +
  "try{var t=localStorage.getItem('famiglia-tema');if(t)r.setAttribute('data-theme',t)}catch(e){}})();";

export function documento(o: Opzioni): string {
  const t = T[o.lingua];
  const c = o.contenuto;
  const url = (p: string) => SITO + p;
  const indicizza = !NOINDEX && !o.noindex;
  const alternati = o.id
    ? `<link rel="canonical" href="${url(PERCORSI[o.id][o.lingua])}">` +
      `<link rel="alternate" hreflang="it" href="${url(PERCORSI[o.id].it)}">` +
      `<link rel="alternate" hreflang="en" href="${url(PERCORSI[o.id].en)}">` +
      `<link rel="alternate" hreflang="x-default" href="${url(PERCORSI[o.id].it)}">`
    : "";
  const og = o.lingua === "it" ? "/sito/og-it.png" : "/sito/og-en.png";
  const ogAlt =
    o.lingua === "it"
      ? "ParliamentRAG: tre garanzie per ogni risposta dell'AI sul Parlamento"
      : "ParliamentRAG: three guarantees for every AI answer about Parliament";
  const script = (o.script ?? []).map((s) => `<script src="${v("/sito/" + s)}"></script>`).join("\n");

  return `<!doctype html>
<html lang="${o.lingua}" class="no-js" data-sito="parliamentrag" data-pagina="${o.voce ?? (o.id === "home" ? "home" : "")}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>${esc(c.titolo)}</title>
<meta name="description" content="${esc(c.descrizione)}">
${indicizza ? "" : '<meta name="robots" content="noindex, nofollow">'}
${alternati}
<meta property="og:type" content="website">
<meta property="og:site_name" content="ParliamentRAG">
<meta property="og:title" content="${esc(c.titolo)}">
<meta property="og:description" content="${esc(c.descrizione)}">
${o.id ? `<meta property="og:url" content="${url(PERCORSI[o.id][o.lingua])}">` : ""}
<meta property="og:locale" content="${t.ogLocale}">
<meta property="og:locale:alternate" content="${o.lingua === "it" ? "en_GB" : "it_IT"}">
<meta property="og:image" content="${url(og)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="${esc(ogAlt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${esc(c.titolo)}">
<meta name="twitter:description" content="${esc(c.descrizione)}">
<meta name="twitter:image" content="${url(og)}">
<meta name="theme-color" media="(prefers-color-scheme: light)" content="#f6f5f1">
<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#0f1315">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="ParliamentRAG">
${AVVIO}
<link rel="preload" href="/sito/font/geist-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/sito/font/newsreader-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/sito/font/newsreader-italic-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/sito/font/geist-mono-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="${v("/sito/font.css")}">
<link rel="stylesheet" href="${v("/sito/famiglia.css")}">
${o.css ? `<link rel="stylesheet" href="${v(`/sito/pagine/${o.css}.css`)}">` : ""}
<script>${SUBITO}</script>
</head>
<body>
<a class="salta" href="#contenuto">${t.salta}</a>
${testata(o)}
<main id="contenuto">
${c.html}
</main>
${piede(o.lingua)}
${script}
</body>
</html>
`;
}

export function rispondi(html: string, stato = 200): Response {
  return new Response(html, {
    status: stato,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      // Il browser ricontrolla a ogni visita: dopo un deploy vede subito la versione nuova
      "Cache-Control": "public, max-age=0, must-revalidate",
    },
  });
}
