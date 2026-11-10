"""Fatti delle commissioni letti nei sommari (committee_fact, pipeline/fatti.py): audizioni, pareri delle commissioni, pareri
del governo e del relatore sugli emendamenti, passaggi dell'iter, risposte alle interrogazioni. Ogni fatto porta la
frase del sommario da cui viene: è scritta dagli uffici, non è parola di un parlamentare."""

from __future__ import annotations

import datetime as dt

import psycopg

TIPI = {"audizione": "hearing", "parere": "opinion", "parere_emendamenti": "amendment_opinion", "iter": "step", "interrogazione": "answer"}
# i tipi che la chat legge: precisione misurata a mano sopra il 95% (10/11/2026). Iter e pareri sugli emendamenti restano
# nella tabella, fuori dalla chat finché una nuova misura non li promuove.
PUBBLICI = ("hearing", "opinion", "answer")


def fatti_commissioni(c: psycopg.Connection, kind: str | None = None, act: str | None = None, subject: str | None = None,
                      body: str | None = None, chamber: str | None = None, start: dt.date | None = None, end: dt.date | None = None,
                      outcome: str | None = None, limit: int = 30, offset: int = 0) -> tuple[int, list[dict]]:
    p = {"k": TIPI.get(kind or "", kind), "a": act, "s": subject, "b": body, "r": chamber, "dal": start, "al": end, "o": outcome,
         "lim": limit, "off": offset, "pub": list(PUBBLICI)}
    filtro = """f.kind = ANY (%(pub)s) AND (%(k)s::text IS NULL OR f.kind = %(k)s)
        AND (%(a)s::text IS NULL OR f.act = %(a)s OR %(a)s = ANY (f.act_refs))
        AND (%(s)s::text IS NULL OR f.subject ILIKE '%%' || %(s)s || '%%')
        AND (%(b)s::text IS NULL OR f.body = %(b)s OR f.body_name ILIKE '%%' || %(b)s || '%%')
        AND (%(r)s::text IS NULL OR f.chamber = %(r)s)
        AND (%(o)s::text IS NULL OR f.outcome = %(o)s)
        AND (%(dal)s::date IS NULL OR f.sitting_date >= %(dal)s) AND (%(al)s::date IS NULL OR f.sitting_date <= %(al)s)"""
    totale = c.execute(f"SELECT count(*) AS n FROM committee_fact f WHERE {filtro}", p).fetchone()["n"]
    righe = c.execute(f"""SELECT f.kind, f.chamber, f.sitting_date, f.body_name, f.sitting, f.speech, f.act, f.act_refs, a.title AS act_title,
               f.subject, f.outcome, f.amendments, f.amendments_found, f.evidence
        FROM committee_fact f LEFT JOIN act a ON a.uri = f.act
        WHERE {filtro} ORDER BY f.sitting_date DESC, f.uri LIMIT %(lim)s OFFSET %(off)s""", p).fetchall()
    return totale, [{k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in r.items() if v not in (None, [])} for r in righe]
