"""Sedute d'Aula e di commissione, con argomenti, interventi, didascalie e votazioni."""

from __future__ import annotations

import datetime as dt

import psycopg

from ..modelli import ActRef, AgendaItem, Reaction, Sitting, SittingBrief, Speech
from .comune import brevi
from .voti import SQL_VOTO_BREVE, voto_breve

CAMPI_BREVI = "uri, chamber, body, body_name, number, date, kind, status"


def elenco_sedute(c: psycopg.Connection, chamber: str | None = None, body: str | None = None, start: dt.date | None = None,
                  end: dt.date | None = None, limit: int = 50, offset: int = 0) -> tuple[int, list[SittingBrief]]:
    """Sedute dalla più recente. `body`: «aula», «commissioni» o l'uri di un organo."""
    filtro = """(%(ramo)s::text IS NULL OR chamber = %(ramo)s)
        AND (%(org)s::text IS NULL OR (%(org)s = 'aula' AND body LIKE '%%:aula') OR (%(org)s = 'commissioni' AND body NOT LIKE '%%:aula')
             OR body = %(org)s)
        AND (%(dal)s::date IS NULL OR date >= %(dal)s) AND (%(al)s::date IS NULL OR date <= %(al)s)"""
    p = {"ramo": chamber, "org": body, "dal": start, "al": end, "lim": limit, "off": offset}
    totale = c.execute(f"SELECT count(*) AS n FROM sitting WHERE {filtro}", p).fetchone()["n"]
    righe = c.execute(f"SELECT {CAMPI_BREVI} FROM sitting WHERE {filtro} ORDER BY date DESC, number DESC LIMIT %(lim)s OFFSET %(off)s", p)
    return totale, [SittingBrief(**r) for r in righe]


def seduta(c: psycopg.Connection, uri: str) -> Sitting | None:
    s = c.execute("SELECT * FROM sitting WHERE uri = %s", (uri,)).fetchone()
    if not s:
        return None
    punti = c.execute("SELECT uri, ord, title, stage FROM agenda_item WHERE sitting = %s ORDER BY ord", (uri,)).fetchall()
    atti: dict[str, list[ActRef]] = {}
    for a in c.execute("""SELECT x.item, x.act_ref, x.act, a.title FROM agenda_item_act x JOIN agenda_item i ON i.uri = x.item
                          LEFT JOIN act a ON a.uri = x.act WHERE i.sitting = %s ORDER BY x.act_ref""", (uri,)):
        atti.setdefault(a["item"], []).append(ActRef(ref=a["act_ref"], uri=a["act"], title=a["title"]))
    interventi = c.execute("""SELECT s.uri, s.item, s.ord, s.person, s.speaker_label, s.as_group, s.as_office, s.kind, s.text
                              FROM speech s JOIN agenda_item i ON i.uri = s.item WHERE i.sitting = %s ORDER BY i.ord, s.ord""", (uri,)).fetchall()
    reazioni: dict[str, list[Reaction]] = {}
    for r in c.execute("""SELECT r.speech, r.kind, r.raw, r.offset_char FROM reaction r JOIN speech s ON s.uri = r.speech
                          JOIN agenda_item i ON i.uri = s.item WHERE i.sitting = %s ORDER BY r.offset_char""", (uri,)):
        reazioni.setdefault(r["speech"], []).append(Reaction(kind=r["kind"], raw=r["raw"], offset_char=r["offset_char"]))
    persone = brevi(c, [x["person"] for x in interventi], s["date"])
    per_punto: dict[str, list[Speech]] = {}
    for x in interventi:
        per_punto.setdefault(x["item"], []).append(Speech(
            uri=x["uri"], order=x["ord"], person=persone.get(x["person"]), speaker_label=x["speaker_label"], as_group=x["as_group"],
            as_office=x["as_office"], kind=x["kind"], text=x["text"], reactions=reazioni.get(x["uri"], [])))
    voti = [voto_breve(v) for v in c.execute(SQL_VOTO_BREVE + " WHERE v.sitting = %s ORDER BY v.number", (uri,))]
    return Sitting(**{k: s[k] for k in SittingBrief.model_fields}, seat=s["seat"], presided_by=s["presided_by"],
                   start_time=s["start_time"], end_time=s["end_time"],
                   items=[AgendaItem(uri=p["uri"], order=p["ord"], title=p["title"], stage=p["stage"], acts=atti.get(p["uri"], []),
                                     speeches=per_punto.get(p["uri"], [])) for p in punti],
                   votes=voti)
