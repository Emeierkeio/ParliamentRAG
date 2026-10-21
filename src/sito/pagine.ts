/*
 * Ogni pagina: contenuto nelle due lingue, foglio di stile, script.
 * Gli script stanno in public/sito/ e girano nell'ordine dato.
 */
import { documento, esc, rispondi, type Contenuto } from "./guscio";
import { legale } from "./legale";
import { riempi } from "./dinamici";
import { percorso, type IdPagina, type Lingua } from "./rotte";

import homeIt from "./pagine/it/home";
import metodoIt from "./pagine/it/metodo";
import verificaIt from "./pagine/it/verifica";
import datiIt from "./pagine/it/dati";
import ricercaIt from "./pagine/it/ricerca";
import sviluppatoriIt from "./pagine/it/sviluppatori";
import aggiornamentiIt from "./pagine/it/aggiornamenti";
import homeEn from "./pagine/en/home";
import metodoEn from "./pagine/en/metodo";
import verificaEn from "./pagine/en/verifica";
import datiEn from "./pagine/en/dati";
import ricercaEn from "./pagine/en/ricerca";
import sviluppatoriEn from "./pagine/en/sviluppatori";
import aggiornamentiEn from "./pagine/en/aggiornamenti";

type Pagina = {
  contenuto: (l: Lingua) => Contenuto;
  css?: string;
  script: string[];
  voce?: IdPagina;
  noindex?: boolean;
};

const coppia = (it: Contenuto, en: Contenuto) => (l: Lingua) => (l === "it" ? it : en);
/* Pagine con parti scritte dai dati al build (src/sito/dinamici.ts) */
const conDati = (pagina: "home" | "dati", it: Contenuto, en: Contenuto) => (l: Lingua) => {
  const c = l === "it" ? it : en;
  return { ...c, html: riempi(c.html, pagina, l) };
};

const PAGINE: Record<IdPagina, Pagina> = {
  home: {
    contenuto: conDati("home", homeIt, homeEn),
    css: "home",
    script: ["dati.js", "aula.js", "famiglia.js", "iscrizione.js", "pagine/home.js"],
  },
  metodo: {
    contenuto: coppia(metodoIt, metodoEn),
    css: "metodo",
    script: ["dati.js", "famiglia.js", "pagine/metodo.js"],
    voce: "metodo",
  },
  verifica: {
    contenuto: coppia(verificaIt, verificaEn),
    css: "verifica",
    script: ["dati.js", "famiglia.js", "pagine/verifica.js"],
    voce: "verifica",
  },
  dati: {
    contenuto: conDati("dati", datiIt, datiEn),
    css: "dati",
    script: ["dati.js", "famiglia.js", "pagine/dati.js"],
    voce: "dati",
  },
  ricerca: {
    contenuto: coppia(ricercaIt, ricercaEn),
    css: "ricerca",
    script: ["famiglia.js", "iscrizione.js", "pagine/ricerca.js"],
    voce: "ricerca",
  },
  sviluppatori: {
    contenuto: coppia(sviluppatoriIt, sviluppatoriEn),
    css: "sviluppatori",
    script: ["famiglia.js", "pagine/sviluppatori.js"],
    voce: "sviluppatori",
  },
  aggiornamenti: {
    contenuto: coppia(aggiornamentiIt, aggiornamentiEn),
    css: "aggiornamenti",
    script: ["famiglia.js", "iscrizione.js", "pagine/aggiornamenti.js"],
    voce: "aggiornamenti",
  },
  privacy: {
    contenuto: (l) => legale("privacy", l),
    css: "legale",
    script: ["famiglia.js", "pagine/legale.js"],
  },
  termini: {
    contenuto: (l) => legale("termini", l),
    css: "legale",
    script: ["famiglia.js", "pagine/legale.js"],
  },
  confermata: {
    contenuto: (l) => confermata(l),
    css: "esito",
    script: ["famiglia.js"],
    noindex: true,
  },
};

export function pagina(id: IdPagina, lingua: Lingua): string {
  const p = PAGINE[id];
  return documento({
    id,
    lingua,
    contenuto: p.contenuto(lingua),
    css: p.css,
    script: p.script,
    voce: p.voce,
    noindex: p.noindex,
  });
}

const FRECCIA =
  '<svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg>';

/* Una pagina breve con un esito: conferma della newsletter e pagina non trovata */
function esito(o: { etichetta: string; titolo: string; testo: string; azioni: string; seguito?: string }): string {
  return `
  <section class="apertura esito-pagina">
    <div class="pagina">
      <p class="etichetta compare">${o.etichetta}</p>
      <h1 class="titolo-1 compare" style="--ritardo:80ms">${o.titolo}</h1>
      <p class="attacco compare" style="--ritardo:160ms">${o.testo}</p>
      <div class="fila esito-pagina__azioni compare" style="--ritardo:240ms">${o.azioni}</div>
      ${o.seguito ?? ""}
    </div>
  </section>
`;
}

function confermata(l: Lingua): Contenuto {
  const p = (id: IdPagina) => percorso(id, l);
  const it = l === "it";
  const voci: [IdPagina, string, string][] = it
    ? [
        ["metodo", "Metodo", "Come verifichiamo una risposta sul Parlamento."],
        ["dati", "Dati", "Il grafo di Camera e Senato, da scaricare."],
        ["ricerca", "Ricerca", "Gli articoli a ISWC 2026 e come citarli."],
      ]
    : [
        ["metodo", "Method", "How we check an answer about Parliament."],
        ["dati", "Data", "The graph of the Chamber and the Senate, ready to download."],
        ["ricerca", "Research", "The ISWC 2026 papers and how to cite them."],
      ];
  return {
    titolo: it ? "Iscrizione confermata · ParliamentRAG" : "Subscription confirmed · ParliamentRAG",
    descrizione: it
      ? "Hai confermato l'iscrizione agli aggiornamenti di ParliamentRAG."
      : "You have confirmed your subscription to ParliamentRAG updates.",
    html: esito({
      etichetta: it ? "Aggiornamenti" : "Updates",
      titolo: it ? "Iscrizione confermata." : "Subscription confirmed.",
      testo: it
        ? "Riceverai le novità di ParliamentRAG. In fondo a ogni email trovi il link per cancellarti."
        : "You will receive ParliamentRAG news. Every email ends with an unsubscribe link.",
      azioni: `<a class="btn btn--accento" href="${p("home")}">${it ? "Torna alla pagina iniziale" : "Back to the home page"} ${FRECCIA}</a>`,
      seguito:
        `<div class="esito-pagina__poi compare" style="--ritardo:320ms"><p class="etichetta">${it ? "Intanto puoi leggere" : "Meanwhile, you can read"}</p><ul>` +
        voci.map(([id, t, d]) => `<li><a href="${p(id)}"><strong>${t}</strong><span>${esc(d)}</span></a></li>`).join("") +
        "</ul></div>",
    }),
  };
}

export function nonTrovata(l: Lingua): string {
  const it = l === "it";
  return documento({
    id: null,
    lingua: l,
    css: "esito",
    script: ["famiglia.js"],
    noindex: true,
    contenuto: {
      titolo: it ? "Pagina non trovata · ParliamentRAG" : "Page not found · ParliamentRAG",
      descrizione: it ? "Questa pagina non esiste." : "This page does not exist.",
      html: esito({
        etichetta: "404",
        titolo: it ? "Questa pagina non c'è." : "This page does not exist.",
        testo: it
          ? "Forse l'indirizzo è cambiato con il nuovo sito. Le pagine del progetto sono tutte nel menu in alto."
          : "The address may have changed with the new site. All the project's pages are in the menu at the top.",
        azioni:
          `<a class="btn btn--accento" href="${percorso("home", l)}">${it ? "Vai alla pagina iniziale" : "Go to the home page"} ${FRECCIA}</a>` +
          `<a class="btn btn--linea" href="${percorso("metodo", l)}">${it ? "Il metodo" : "The method"}</a>`,
      }),
    },
  });
}

/** Risposta di una pagina, per i route handler in src/app */
export function servi(id: IdPagina, lingua: Lingua): Response {
  return rispondi(pagina(id, lingua));
}
