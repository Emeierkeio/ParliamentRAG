"""Documenti depositati in commissione (tabella document): memorie delle audizioni, contributi scritti sugli atti, allegati
del Bollettino, dossier, e gli stenografici delle commissioni del Senato (che esistono solo in PDF). Due usi: l'elenco per atto, autore, commissione e date, e la lettura del testo di un documento,
a pagine. Le memorie e i contributi sono scritti di terzi (associazioni, aziende, autorità): non sono parole di un
parlamentare, vanno riferiti attribuendoli a chi li ha mandati, con il link al file ufficiale."""

from __future__ import annotations

import datetime as dt
import re

import psycopg

TIPI = {"memoria": "memorandum", "contributo": "written_contribution", "allegato": "annex", "dossier": "dossier",
        "stenografico": "verbatim_record"}
PAGINA = 11000                          # caratteri di testo per lettura: sta nel taglio che l'agente applica ai risultati


def riferimento(atto: str | None) -> str | None:
    """it:camera:19:ac:3120 -> ac:3120, come gli atti sono scritti in document.acts; un riferimento resta com'è."""
    if atto and atto.startswith("it:"):
        return ":".join(atto.split(":")[-2:])
    return atto


def indirizzo(url: str | None) -> str | None:
    """I file della Camera hanno spazi nel nome («Contributo Scritto»): in un link Markdown lo spazio lo spezza e il
    controllo dei link lo toglierebbe, quindi qui diventa %20."""
    return url.replace(" ", "%20") if url else url


def _riga(r: dict) -> dict:
    if r.get("url"):
        r = {**r, "url": indirizzo(r["url"])}
    return {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in r.items() if v not in (None, [], "")}


def documenti(c: psycopg.Connection, act: str | None = None, author: str | None = None, body: str | None = None,
              kind: str | None = None, q: str | None = None, start: dt.date | None = None, end: dt.date | None = None,
              limit: int = 25, offset: int = 0, text: str | None = None) -> tuple[int, list[dict]]:
    """`text` cerca le parole dentro il testo dei documenti (ricerca in italiano, sintassi web): ogni riga porta allora un
    estratto del punto in cui compaiono; l'ordine resta dal più recente."""
    p = {"a": act, "rif": riferimento(act), "au": author, "b": body, "k": TIPI.get(kind or "", kind), "q": q,
         "dal": start, "al": end, "lim": limit, "off": offset, "t": text}
    # le memorie delle audizioni non portano l'atto: si legano all'atto dall'audizione dello stesso giorno nella stessa
    # commissione (committee_fact); il campo hearing dice di quale audizione si tratta
    filtro = """(%(a)s::text IS NULL OR %(a)s = ANY (d.acts) OR %(rif)s = ANY (d.acts)
             OR (d.kind = 'memorandum' AND EXISTS (SELECT 1 FROM committee_fact f WHERE f.kind = 'hearing' AND f.body = d.body
                 AND f.sitting_date = d.sitting_date AND (f.act = %(a)s OR %(rif)s = ANY (f.act_refs)))))
        AND (%(au)s::text IS NULL OR coalesce(d.author_raw, d.title, '') ILIKE '%%' || %(au)s || '%%')
        AND (%(b)s::text IS NULL OR d.body = %(b)s OR o.name ILIKE '%%' || %(b)s || '%%')
        AND (%(k)s::text IS NULL OR d.kind = %(k)s)
        AND (%(q)s::text IS NULL OR concat_ws(' ', d.title, d.author_raw, d.hearing) ILIKE '%%' || %(q)s || '%%')
        AND (%(dal)s::date IS NULL OR coalesce(d.date, d.sitting_date) >= %(dal)s)
        AND (%(al)s::date IS NULL OR coalesce(d.date, d.sitting_date) <= %(al)s)"""
    # parole nel testo: l'indice trova i documenti che hanno tutte le parole; una «frase esatta» si controlla poi sul testo
    # con ILIKE, perché farla controllare all'indice vuol dire rileggere ogni documento candidato (decine di secondi)
    frasi, estratto = "", "NULL::text AS snippet"
    if text:
        esatte = [f.strip() for f in re.findall(r'"([^"]+)"', text) if f.strip()]
        p["t"] = text.replace('"', " ")
        filtro += " AND to_tsvector('italian', coalesce(d.text, '')) @@ websearch_to_tsquery('italian', %(t)s)"
        for k, f in enumerate(esatte):
            p[f"f{k}"] = f
            frasi += f" AND d.text ILIKE '%%' || %(f{k})s || '%%'"
        # l'estratto: il testo intorno alla prima occorrenza della frase, o dell'inizio della parola più lunga; si guarda nei
        # primi 400 mila caratteri, perché i dossier arrivano a qualche milione
        parole = [w for w in re.findall(r"[^\W\d_]{4,}", re.sub(r"-\S+", " ", p["t"])) if w.lower() != "or"]
        lunga = max(parole, key=len) if parole else ""
        p["ago"] = (esatte[0] if esatte else lunga[:max(5, len(lunga) - 2)]).lower()
        estratto = ("btrim(regexp_replace(substr(d.text, greatest(1, position(%(ago)s in lower(left(d.text, 400000))) - 160), 420), "
                    "'\\s+', ' ', 'g')) AS snippet")
    # in tre passi, perché il testo di un documento pesa: prima i documenti che passano i filtri leggeri e l'indice (base),
    # poi la frase esatta solo su quelli, infine lunghezza ed estratto solo per le righe della pagina
    base = f"""WITH base AS MATERIALIZED (
        SELECT d.uri, coalesce(d.date, d.sitting_date) AS giorno FROM document d LEFT JOIN body o ON o.uri = d.body WHERE {filtro}),
      buoni AS MATERIALIZED (SELECT b.uri, b.giorno FROM base b{" JOIN document d ON d.uri = b.uri WHERE true" + frasi if frasi else ""})"""
    # il totale viaggia con le righe: contare a parte rifarebbe il controllo della frase su tutti i candidati
    righe = c.execute(f"""{base},
      pagina AS MATERIALIZED (SELECT uri, giorno FROM buoni ORDER BY giorno DESC NULLS LAST, uri LIMIT %(lim)s OFFSET %(off)s)
    SELECT d.uri, d.kind, d.date, d.sitting_date, o.name AS body, d.author_raw AS author, d.title, d.hearing, d.url,
           length(coalesce(d.text, '')) AS chars, {estratto}, (SELECT count(*) FROM buoni) AS totale
    FROM pagina s JOIN document d ON d.uri = s.uri LEFT JOIN body o ON o.uri = d.body ORDER BY s.giorno DESC NULLS LAST, d.uri""", p).fetchall()
    totale = righe[0]["totale"] if righe else c.execute(f"{base} SELECT count(*) AS n FROM buoni", p).fetchone()["n"]
    righe = [{k: v for k, v in r.items() if k != "totale"} for r in righe]
    # elenco stretto, perché una pagina stia nel taglio dell'agente: il titolo solo se non ripete l'autore, l'audizione solo
    # per le memorie (nei contributi è il titolo dell'atto)
    return totale, [_riga({**r, "title": None if (r["title"] or "") == (r["author"] or "") else (r["title"] or "")[:160],
                           "hearing": (r["hearing"] or "")[:140] if r["kind"] in ("memorandum", "verbatim_record") else None}) for r in righe]


def documento(c: psycopg.Connection, uri: str, offset: int = 0) -> dict | None:
    """Il testo di un documento da `offset`, una pagina per volta; `more` dice da dove riprendere."""
    r = c.execute("""SELECT d.uri, d.kind, d.date, d.sitting_date, o.name AS body, d.author_raw AS author, d.title, d.hearing, d.acts,
               d.format, d.url, d.third_party, length(coalesce(d.text, '')) AS chars, substr(coalesce(d.text, ''), %(o)s + 1, %(n)s) AS text
        FROM document d LEFT JOIN body o ON o.uri = d.body WHERE d.uri = %(u)s""", {"u": uri, "o": offset, "n": PAGINA}).fetchone()
    if r is None:
        return None
    out = _riga(r)
    if not r["chars"]:
        out["note"] = "il testo di questo documento non è stato estratto: rimanda al file ufficiale (url)"
    elif offset + PAGINA < r["chars"]:
        out["more"] = f"testo parziale: caratteri {offset + 1}-{offset + PAGINA} di {r['chars']}; il seguito con offset={offset + PAGINA}"
    if r["third_party"]:
        out["note_autore"] = "scritto di terzi: riferiscilo attribuendolo all'autore, senza «…», con il link (url)"
    if r["kind"] == "verbatim_record":
        out["note_testo"] = ("stenografico di una commissione del Senato, testo estratto dal PDF: gli a capo e gli spazi non sono "
                             "affidabili, quindi riferisci chi ha detto cosa senza «…» e dai il link al PDF (url)")
    return out
