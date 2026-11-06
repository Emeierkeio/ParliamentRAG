"""Ricerca nel testo degli interventi (ricerca in italiano di Postgres, indice speech_fts)."""

from __future__ import annotations

import datetime as dt

import psycopg

from ..modelli import SittingBrief, SpeechHit
from .comune import brevi, stessa_persona, url_interventi


def cerca_interventi(c: psycopg.Connection, q: str, chamber: str | None = None, person: str | None = None,
                     start: dt.date | None = None, end: dt.date | None = None, include_summaries: bool = True,
                     limit: int = 20, offset: int = 0) -> list[SpeechHit]:
    """Interventi che contengono le parole cercate (sintassi di websearch: «"frase esatta"», «-parola», «or»), dal più recente.
    I riassunti delle commissioni (`kind = summary`) non sono parole testuali: si escludono con `include_summaries=False`."""
    from ..fascicolo.recupero_canali import CARICA_GOVERNO
    persone_ids = stessa_persona(c, person) if person else None
    righe = c.execute("""
        WITH q AS (SELECT websearch_to_tsquery('italian', %(q)s) AS q)
        SELECT s.uri, s.person, s.speaker_label, s.kind, i.title AS item_title,
               EXISTS (SELECT 1 FROM office o
                       WHERE o.person IN (SELECT s.person UNION SELECT same_as FROM person_same_as WHERE person = s.person
                                          UNION SELECT person FROM person_same_as WHERE same_as = s.person)
                         AND o.target LIKE 'it:gov:%%' AND o.start_date <= st.date AND (o.end_date IS NULL OR o.end_date >= st.date))
                 AND (s.as_office ~* %(carica)s OR (s.as_group IS NULL AND st.kind = 'assembly_verbatim')) AS governo,
               coalesce(CASE WHEN s.as_office ~* %(carica)s THEN s.as_office END,
                        substring(s.text from '^, *([^.]{3,90})\.')) AS carica,
               st.uri AS st_uri, st.chamber, st.body, st.body_name, st.number, st.date, st.kind AS st_kind, st.status,
               ts_headline('italian', s.text, q.q, 'StartSel=[[, StopSel=]], MaxWords=40, MinWords=15, MaxFragments=2') AS snippet
        FROM speech s CROSS JOIN q JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
        WHERE to_tsvector('italian', s.text) @@ q.q
          AND (%(ramo)s::text IS NULL OR st.chamber = %(ramo)s)
          AND (%(pers)s::text[] IS NULL OR s.person = ANY(%(pers)s))
          AND (%(dal)s::date IS NULL OR st.date >= %(dal)s) AND (%(al)s::date IS NULL OR st.date <= %(al)s)
          AND (%(somm)s OR s.kind IS DISTINCT FROM 'summary')
        ORDER BY st.date DESC, s.uri LIMIT %(lim)s OFFSET %(off)s""",
        {"q": q, "ramo": chamber, "pers": persone_ids, "dal": start, "al": end, "somm": include_summaries, "lim": limit, "off": offset, "carica": CARICA_GOVERNO}).fetchall()
    # il gruppo è quello alla data della seduta: una persona può aver cambiato gruppo da allora
    persone = {(u, d): b for d in {r["date"] for r in righe}
               for u, b in brevi(c, [r["person"] for r in righe if r["date"] == d], d).items()}
    link = url_interventi(c, [r["uri"] for r in righe])
    video = {v["speech"]: v for v in c.execute("""SELECT DISTINCT ON (vs.speech) vs.speech, v.url || coalesce('/' || vs.webtv_id, '') AS url, vs.start_s FROM video_segment vs
                                                    JOIN video v ON v.uri = vs.video WHERE vs.speech = ANY(%s) ORDER BY vs.speech, vs.start_s""",
                                                 ([r["uri"] for r in righe],))}
    return [SpeechHit(uri=r["uri"], item_title=r["item_title"], person=_senza_gruppo(persone.get((r["person"], r["date"])), r["governo"]),
                      speaker_label=r["speaker_label"], kind=r["kind"], snippet=r["snippet"], url=link.get(r["uri"]),
                      government=r["governo"], office=r["carica"] if r["governo"] else None,
                      video=(video.get(r["uri"]) or {}).get("url"), video_start_s=(video.get(r["uri"]) or {}).get("start_s"),
                      sitting=SittingBrief(uri=r["st_uri"], chamber=r["chamber"], body=r["body"], body_name=r["body_name"],
                                           number=r["number"], date=r["date"], kind=r["st_kind"], status=r["status"]))
            for r in righe]


def _senza_gruppo(persona, governo: bool):
    """Chi parla da membro del Governo non parla per il suo gruppo: il gruppo non si passa, così non gli si attribuisce."""
    return persona.model_copy(update={"group": None}) if persona and governo else persona


def totale_interventi(c: psycopg.Connection, q: str, chamber: str | None = None, person: str | None = None,
                      start: dt.date | None = None, end: dt.date | None = None, include_summaries: bool = True) -> int:
    """Quanti interventi contengono le parole, con gli stessi filtri di cerca_interventi."""
    persone_ids = stessa_persona(c, person) if person else None
    return c.execute("""
        SELECT count(*) AS n FROM speech s JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
        WHERE to_tsvector('italian', s.text) @@ websearch_to_tsquery('italian', %(q)s)
          AND (%(ramo)s::text IS NULL OR st.chamber = %(ramo)s) AND (%(pers)s::text[] IS NULL OR s.person = ANY(%(pers)s))
          AND (%(dal)s::date IS NULL OR st.date >= %(dal)s) AND (%(al)s::date IS NULL OR st.date <= %(al)s)
          AND (%(somm)s OR s.kind IS DISTINCT FROM 'summary')""",
        {"q": q, "ramo": chamber, "pers": persone_ids, "dal": start, "al": end, "somm": include_summaries}).fetchone()["n"]


PRIMA_DELLA_DIDASCALIA = 300          # caratteri del parlato prima della didascalia, nell'estratto


def cerca_didascalie(c: psycopg.Connection, q: str, chamber: str | None = None, person: str | None = None,
                     start: dt.date | None = None, end: dt.date | None = None, limit: int = 20,
                     offset: int = 0) -> tuple[int, list[SpeechHit]]:
    """Le didascalie del resoconto (applausi, proteste, «si levano in piedi»…) che contengono tutte le parole cercate,
    dalla più recente. L'estratto è il parlato che la precede, con la didascalia tra «[[(» e «)]]» com'è scritta.
    `person` è chi parla nell'intervento in cui la didascalia compare."""
    parole = [w for w in q.replace('"', " ").split() if w]
    persone_ids = stessa_persona(c, person) if person else None
    filtro = """(SELECT bool_and(r.raw ILIKE '%%' || w || '%%') FROM unnest(%(parole)s::text[]) AS w)
          AND (%(ramo)s::text IS NULL OR st.chamber = %(ramo)s) AND (%(pers)s::text[] IS NULL OR s.person = ANY(%(pers)s))
          AND (%(dal)s::date IS NULL OR st.date >= %(dal)s) AND (%(al)s::date IS NULL OR st.date <= %(al)s)"""
    p = {"parole": parole, "ramo": chamber, "pers": persone_ids, "dal": start, "al": end, "lim": limit, "off": offset,
         "prima": PRIMA_DELLA_DIDASCALIA}
    da = "FROM reaction r JOIN speech s ON s.uri = r.speech JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting"
    totale = c.execute(f"SELECT count(*) AS n {da} WHERE {filtro}", p).fetchone()["n"]
    righe = c.execute(f"""
        SELECT s.uri, s.person, s.speaker_label, s.kind, i.title AS item_title, r.raw,
               substr(s.text, greatest(1, r.offset_char - %(prima)s + 1), least(r.offset_char, %(prima)s)) AS prima,
               st.uri AS st_uri, st.chamber, st.body, st.body_name, st.number, st.date, st.kind AS st_kind, st.status
        {da} WHERE {filtro} ORDER BY st.date DESC, s.uri, r.offset_char LIMIT %(lim)s OFFSET %(off)s""", p).fetchall()
    persone = brevi(c, [r["person"] for r in righe])
    return totale, [SpeechHit(uri=r["uri"], item_title=r["item_title"], person=persone.get(r["person"]), speaker_label=r["speaker_label"],
                              kind=r["kind"], snippet=f"…{r['prima'].strip()} [[({r['raw']})]]",
                              sitting=SittingBrief(uri=r["st_uri"], chamber=r["chamber"], body=r["body"], body_name=r["body_name"],
                                                   number=r["number"], date=r["date"], kind=r["st_kind"], status=r["status"]))
                    for r in righe]
