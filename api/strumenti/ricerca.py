"""Ricerca nel testo degli interventi (ricerca in italiano di Postgres, indice speech_fts)."""

from __future__ import annotations

import datetime as dt

import psycopg

from ..modelli import SittingBrief, SpeechHit
from .comune import brevi, stessa_persona


def cerca_interventi(c: psycopg.Connection, q: str, chamber: str | None = None, person: str | None = None,
                     start: dt.date | None = None, end: dt.date | None = None, include_summaries: bool = True,
                     limit: int = 20, offset: int = 0) -> list[SpeechHit]:
    """Interventi che contengono le parole cercate (sintassi di websearch: «"frase esatta"», «-parola», «or»), dal più recente.
    I riassunti delle commissioni (`kind = summary`) non sono parole testuali: si escludono con `include_summaries=False`."""
    persone_ids = stessa_persona(c, person) if person else None
    righe = c.execute("""
        WITH q AS (SELECT websearch_to_tsquery('italian', %(q)s) AS q)
        SELECT s.uri, s.person, s.speaker_label, s.kind, i.title AS item_title,
               st.uri AS st_uri, st.chamber, st.body, st.body_name, st.number, st.date, st.kind AS st_kind, st.status,
               ts_headline('italian', s.text, q.q, 'StartSel=[[, StopSel=]], MaxWords=40, MinWords=15, MaxFragments=2') AS snippet
        FROM speech s CROSS JOIN q JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
        WHERE to_tsvector('italian', s.text) @@ q.q
          AND (%(ramo)s::text IS NULL OR st.chamber = %(ramo)s)
          AND (%(pers)s::text[] IS NULL OR s.person = ANY(%(pers)s))
          AND (%(dal)s::date IS NULL OR st.date >= %(dal)s) AND (%(al)s::date IS NULL OR st.date <= %(al)s)
          AND (%(somm)s OR s.kind IS DISTINCT FROM 'summary')
        ORDER BY st.date DESC, s.uri LIMIT %(lim)s OFFSET %(off)s""",
        {"q": q, "ramo": chamber, "pers": persone_ids, "dal": start, "al": end, "somm": include_summaries, "lim": limit, "off": offset}).fetchall()
    persone = brevi(c, [r["person"] for r in righe])
    return [SpeechHit(uri=r["uri"], item_title=r["item_title"], person=persone.get(r["person"]), speaker_label=r["speaker_label"],
                      kind=r["kind"], snippet=r["snippet"],
                      sitting=SittingBrief(uri=r["st_uri"], chamber=r["chamber"], body=r["body"], body_name=r["body_name"],
                                           number=r["number"], date=r["date"], kind=r["st_kind"], status=r["status"]))
            for r in righe]
