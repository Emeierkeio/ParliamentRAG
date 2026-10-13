/*
 * Privacy e termini: il testo sta in messages/<lingua>.json (Privacy, Terms),
 * lo stesso degli altri siti della famiglia. Qui diventa la pagina del
 * prototipo: indice numerato, sezioni con ancora, link a email e siti.
 */
import it from "../../messages/it.json";
import en from "../../messages/en.json";
import { esc, type Contenuto } from "./guscio";
import { percorso, type Lingua } from "./rotte";

type Sezione = { h: string; id?: string; p: string[] };
type Documento = { metaTitle: string; title: string; updated: string; sections: Sezione[] };

const MESSAGGI = { it, en } as const;

const DESCRIZIONI = {
  it: {
    privacy: "Informativa sulla privacy di ParliamentRAG: dati trattati, finalità, fornitori, conservazione e diritti.",
    termini: "Termini d'uso di ParliamentRAG: chi gestisce il sito, licenza dei dati, uso consentito, garanzie.",
  },
  en: {
    privacy: "ParliamentRAG privacy notice: data processed, purposes, providers, retention and rights.",
    termini: "ParliamentRAG terms of use: who runs the site, data licence, permitted use, warranties.",
  },
};

/* «Trasferimenti fuori dall'UE» → «trasferimenti-fuori-dall-ue» */
function ancora(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/* Email e indirizzi web nel testo diventano link */
function collega(testo: string): string {
  return esc(testo).replace(
    /([\w.+-]+@[\w-]+\.[\w.]+[a-z])|\b((?:www\.)[\w-]+(?:\.[\w-]+)+(?:\/[\w/-]*)?|dati\.camera\.it)/g,
    (_, email: string | undefined, web: string | undefined) =>
      email ? `<a href="mailto:${email}">${email}</a>` : `<a href="https://${web}" rel="noopener">${web}</a>`,
  );
}

/* Le voci della memoria del browser: il nome della chiave in monospazio */
const CHIAVE = /^([A-Za-z_-]+)(?: (e|and) ([A-Za-z_-]+))? \((?=cookie|memoria|local|session)/;
function paragrafo(testo: string): string {
  const m = testo.match(CHIAVE);
  if (!m) return `<p>${collega(testo)}</p>`;
  const nomi = m[3] ? `<code>${m[1]}</code> ${m[2]} <code>${m[3]}</code>` : `<code>${m[1]}</code>`;
  return `<p class="chiave">${nomi} ${collega(testo.slice(m[0].length - 1))}</p>`;
}

export function legale(tipo: "privacy" | "termini", lingua: Lingua): Contenuto {
  const d = (MESSAGGI[lingua] as unknown as Record<string, Documento>)[tipo === "privacy" ? "Privacy" : "Terms"];
  const sezioni = d.sections.map((s, i) => ({ ...s, ancora: s.id ?? ancora(s.h), n: String(i + 1).padStart(2, "0") }));
  const it = lingua === "it";
  const altro =
    tipo === "privacy"
      ? { href: percorso("termini", lingua), t: it ? "Termini d'uso" : "Terms of use" }
      : { href: percorso("privacy", lingua), t: it ? "Informativa sulla privacy" : "Privacy notice" };

  const html = `
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina">
      <p class="etichetta compare">${it ? "Note legali" : "Legal"}</p>
      <h1 class="titolo-1 compare" style="--ritardo:80ms">${esc(d.title)}</h1>
      <p class="apertura__agg compare" style="--ritardo:160ms">${esc(d.updated)}</p>
    </div>
  </section>

  <!-- Documento -->
  <div class="pagina documento">
    <nav class="indice" aria-label="${it ? "Indice" : "Contents"}">
      <p class="etichetta">${it ? "Indice" : "Contents"}</p>
      <ol id="indice">
${sezioni.map((s) => `          <li><a href="#${s.ancora}"><span>${s.n}</span>${esc(s.h)}</a></li>`).join("\n")}
      </ol>
    </nav>

    <article class="articoli-legali" id="articoli">
${sezioni
  .map(
    (s) => `      <section class="articolo-legale" id="${s.ancora}" aria-labelledby="${s.ancora}-h">
        <h2 id="${s.ancora}-h"><span class="articolo-legale__n">${s.n}</span>${esc(s.h)}</h2>
        <div class="prosa">
${s.p.map((p) => `          ${paragrafo(p)}`).join("\n")}
        </div>
      </section>
`,
  )
  .join("\n")}
      <div class="documento__fine">
        <p class="mono">${esc(d.updated)}</p>
        <p><a class="collegamento" href="${altro.href}">${altro.t}</a></p>
      </div>
    </article>
  </div>
`;
  return {
    titolo: `${d.metaTitle} · ParliamentRAG`,
    descrizione: DESCRIZIONI[lingua][tipo],
    html,
  };
}
