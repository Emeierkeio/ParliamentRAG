"""Ricerca per significato: i brani più vicini a un testo (pgvector su passage_vector, recupero.vicini), per la chat.

Serve quando le parole esatte non bastano: un tema («cosa si è detto sul caro affitti»), sinonimi, una frase detta in
un altro modo. Per gli interventi restituisce chi parla con il gruppo alla data (il Misto per componente), la seduta e
il link al resoconto; per atti, documenti ed emendamenti il titolo, la data e la pagina ufficiale. Il vettore del testo
costa una chiamata a OpenAI (text-embedding-3-large), contata nella spesa del giorno."""

from __future__ import annotations

import datetime as dt

import psycopg

# le fonti della chat -> le fonti dei brani (passage.source)
FONTI = {"interventi": ("speech",), "atti": ("act", "act_title", "act_text"), "documenti": ("document",),
         "emendamenti": ("amendment",)}
TESTO_MASSIMO = 700                     # caratteri di brano restituiti
# un brano sotto questa similarità (scala (1 + cos) / 2) non è sul tema: la stessa soglia del canale denso del fascicolo
# (recupero.PARAMETRI["denso_soglia"], tarata sulle domande della prova pilota: i vicini delle domande sul Parlamento
# stanno sopra 0,71, quelli delle domande fuori dominio fra 0,62 e 0,67)
SOGLIA = 0.68


def _gruppo(e: dict) -> str | None:
    s = e["speaker"]
    if e["governo"]:
        return "Governo"
    if s.get("componente"):
        return f"{s['componente']} (Misto)"
    return s.get("gruppo")


def _interventi(c, vettore: str, rami: list[str], da, a, quanti: int) -> list[dict]:
    from ..fascicolo.recupero import vicini
    from ..fascicolo.recupero_canali import interventi
    from ..fascicolo.recupero_gruppi import partiti_attesi
    brani = vicini(c, vettore, ["speech"], quanti * 2, rami=rami, da=da, a=a, solo_parlamentari=True)
    brani = [b for b in brani if b["similarita"] >= SOGLIA]
    out, visti = [], set()
    for e in interventi(c, brani, partiti_attesi(c, rami)):
        if e["speech_uri"] in visti:                    # un brano per intervento: più voci, non lo stesso discorso
            continue
        visti.add(e["speech_uri"])
        out.append({"fonte": "intervento", "uri": e["speech_uri"], "testo": e["text"][:TESTO_MASSIMO],
                    "chi": e["speaker"]["nome"], "persona": e["speaker"]["uri"], "gruppo": _gruppo(e),
                    "carica": e["speaker"].get("carica"), "ramo": e["chamber"], "data": e["date"],
                    "seduta": e["sitting_number"], "organo": e["body"], "dibattito": e["debate"],
                    "riassunto": e["kind"] == "summary", "url": e["url"], "similarita": round(e["similarita"], 3)})
        if len(out) >= quanti:
            break
    return out


SQL_ALTRI = """
SELECT x.source, x.uri, x.ord, x.start_char, x.end_char,
       coalesce(a.title, at_a.title, d.title, 'Emendamento ' || m.number || ' (' || m.act || ')') AS titolo,
       coalesce(a.date, at_a.date, d.date, m.presented, m.sitting_date) AS data,
       coalesce(a.chamber, at_a.chamber, split_part(x.uri, ':', 2)) AS ramo,
       coalesce(a.card_url, at_a.card_url, d.url) AS url,
       coalesce(a.uri, at_a.uri, m.act) AS atto, m.outcome AS esito,
       substr(CASE x.source WHEN 'act' THEN a.text WHEN 'act_title' THEN a.title WHEN 'act_text' THEN t.text
                            WHEN 'document' THEN d.text ELSE m.text END, x.start_char + 1, x.end_char - x.start_char) AS testo
FROM unnest(%(src)s::text[], %(uri)s::text[], %(ord)s::int[], %(s)s::int[], %(e)s::int[]) AS x(source, uri, ord, start_char, end_char)
LEFT JOIN act a ON x.source IN ('act', 'act_title') AND a.uri = x.uri
LEFT JOIN act_text t ON x.source = 'act_text' AND t.code = x.uri
LEFT JOIN act at_a ON at_a.uri = t.act
LEFT JOIN document d ON x.source = 'document' AND d.uri = x.uri
LEFT JOIN amendment m ON x.source = 'amendment' AND m.uri = x.uri"""

NOMI = {"act": "atto", "act_title": "atto", "act_text": "testo di un atto", "document": "documento", "amendment": "emendamento"}


def _altri(c, vettore: str, fonti: list[str], rami: list[str], da, a, quanti: int) -> list[dict]:
    from ..fascicolo.recupero import vicini
    k = quanti * (6 if da or a else 2)                  # le date si filtrano dopo: se ne prendono di più
    brani = [b for b in vicini(c, vettore, fonti, k, rami=rami) if b["similarita"] >= SOGLIA]
    if not brani:
        return []
    col = {k: [b[k] for b in brani] for k in ("source", "uri", "ord", "start_char", "end_char")}
    info = {(r["source"], r["uri"], r["ord"]): r for r in c.execute(SQL_ALTRI, {
        "src": col["source"], "uri": col["uri"], "ord": col["ord"], "s": col["start_char"], "e": col["end_char"]})}
    out, visti = [], set()
    for b in brani:
        r = info.get((b["source"], b["uri"], b["ord"]))
        if r is None or (r["atto"] or b["uri"]) in visti:
            continue
        if (da and (r["data"] is None or r["data"] < da)) or (a and (r["data"] is None or r["data"] > a)):
            continue
        visti.add(r["atto"] or b["uri"])
        out.append({"fonte": NOMI.get(b["source"], b["source"]), "uri": b["uri"], "atto": r["atto"],
                    "titolo": (r["titolo"] or "")[:300], "testo": (r["testo"] or "")[:TESTO_MASSIMO],
                    "ramo": r["ramo"], "data": r["data"].isoformat() if r["data"] else None, "esito": r["esito"],
                    "url": (r["url"] or "").replace(" ", "%20") or None,     # file della Camera con spazi nel nome
                    "similarita": round(b["similarita"], 3)})
        if len(out) >= quanti:
            break
    return out


def cerca(c: psycopg.Connection, testo: str, fonti: list[str], ramo: str | None = None, da: dt.date | None = None,
          a: dt.date | None = None, quanti: int = 10) -> dict:
    """I brani più vicini a `testo` fra le fonti chieste (interventi, atti, documenti, emendamenti), dal più vicino.
    `da`/`a` limitano le date (della seduta per gli interventi, dell'atto o del documento per il resto)."""
    from ..fascicolo import modello
    rami = [ramo] if ramo else ["camera", "senato"]
    vettore = modello.letterale(modello.vettori([testo])[0])
    fonti = list(dict.fromkeys(fonti or ["interventi"]))
    risultati: list[dict] = []
    if "interventi" in fonti:
        risultati += _interventi(c, vettore, rami, da, a, quanti)
    altre = [s for f in fonti if f != "interventi" for s in FONTI.get(f, ())]
    if altre:
        risultati += _altri(c, vettore, altre, rami, da, a, quanti)
    risultati.sort(key=lambda r: -r["similarita"])
    return {"testo": testo, "fonti": fonti, "rami": rami, "risultati": risultati[:quanti] if len(fonti) > 1 else risultati,
            "nota": "brani per vicinanza di significato, non per parole: controlla che parlino davvero del tema; "
                    "i riassunti (riassunto: true) non si citano tra «…»"}
