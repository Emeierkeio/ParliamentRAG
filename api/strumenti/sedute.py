"""Sedute d'Aula e di commissione, con argomenti, interventi, didascalie e votazioni."""

from __future__ import annotations

import datetime as dt

import psycopg

from ..modelli import ActRef, AgendaItem, Reaction, Sitting, SittingBrief, Speech
from .comune import brevi, url_seduta, url_sedute
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
    righe = c.execute(f"SELECT {CAMPI_BREVI} FROM sitting WHERE {filtro} ORDER BY date DESC, number DESC LIMIT %(lim)s OFFSET %(off)s", p).fetchall()
    link = url_sedute(c, [r["uri"] for r in righe])
    return totale, [SittingBrief(**r, url=url_seduta(r["uri"], r["status"], r["kind"], link.get(r["uri"]))) for r in righe]


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
    return Sitting(**{k: s[k] for k in SittingBrief.model_fields if k != "url"},
                   url=url_seduta(s["uri"], s["status"], s["kind"], s.get("record_url")), seat=s["seat"], presided_by=s["presided_by"],
                   start_time=s["start_time"], end_time=s["end_time"],
                   items=[AgendaItem(uri=p["uri"], order=p["ord"], title=p["title"], stage=p["stage"], acts=atti.get(p["uri"], []),
                                     speeches=per_punto.get(p["uri"], [])) for p in punti],
                   votes=voti)


def argomenti(c: psycopg.Connection, chamber: str | None = None, body: str | None = None, seat: str | None = None,
              stage: str | None = None, q: str | None = None, start: dt.date | None = None, end: dt.date | None = None,
              limit: int = 50, offset: int = 0) -> dict:
    """I punti all'ordine del giorno delle sedute (Aula e Bollettino delle commissioni), dal più recente, per organo (nome
    o uri), sede («SEDE LEGISLATIVA», «ATTI DELL'UNIONE EUROPEA»), fase («approvazione», «conclusione») e parole del
    titolo; con gli atti collegati e chi è intervenuto."""
    filtro = """(%(ramo)s::text IS NULL OR s.chamber = %(ramo)s)
        AND (%(org)s::text IS NULL OR s.body = %(org)s OR s.body_name ILIKE '%%' || %(org)s || '%%'
             OR (%(org)s = 'aula' AND s.body LIKE '%%:aula')
             OR s.body IN (SELECT o.uri FROM body o WHERE o.name ILIKE '%%' || %(org)s || '%%'))
        AND (%(sede)s::text IS NULL OR s.seat ILIKE '%%' || %(sede)s || '%%')
        AND (%(fase)s::text IS NULL OR i.stage ILIKE '%%' || %(fase)s || '%%')
        AND (%(q)s::text IS NULL OR i.title ILIKE '%%' || %(q)s || '%%'
             OR to_tsvector('italian', coalesce(i.title, '')) @@ websearch_to_tsquery('italian', %(q)s))
        AND (%(dal)s::date IS NULL OR s.date >= %(dal)s) AND (%(al)s::date IS NULL OR s.date <= %(al)s)"""
    p = {"ramo": chamber, "org": body, "sede": seat, "fase": stage, "q": q, "dal": start, "al": end, "lim": limit, "off": offset}
    totale = c.execute(f"SELECT count(*) AS n FROM agenda_item i JOIN sitting s ON s.uri = i.sitting WHERE {filtro}", p).fetchone()["n"]
    righe = c.execute(f"""SELECT i.uri, i.title, i.stage, s.uri AS sitting, s.date, s.chamber, s.body_name, s.seat, s.number,
                                 s.status, s.kind
                          FROM agenda_item i JOIN sitting s ON s.uri = i.sitting WHERE {filtro}
                          ORDER BY s.date DESC, s.number DESC, i.ord LIMIT %(lim)s OFFSET %(off)s""", p).fetchall()
    uris = [r["uri"] for r in righe]
    atti: dict[str, list[dict]] = {}
    for a in c.execute("""SELECT x.item, x.act_ref, x.act, a.title, a.status, a.law_number, a.law_date FROM agenda_item_act x
                          LEFT JOIN act a ON a.uri = x.act WHERE x.item = ANY(%s) ORDER BY x.act_ref""", (uris,)):
        atti.setdefault(a["item"], []).append({"ref": a["act_ref"], "uri": a["act"], "title": a["title"], "status": a["status"],
                                               "law": f"{a['law_number']}/{a['law_date'].year}" if a["law_number"] and a["law_date"] else None})
    oratori: dict[str, list[str]] = {}
    for x in c.execute("""SELECT s.item, s.person, s.speaker_label, min(s.ord) AS o FROM speech s WHERE s.item = ANY(%s)
                          AND s.as_office IS DISTINCT FROM 'PRESIDENTE' GROUP BY 1, 2, 3 ORDER BY 1, 4""", (uris,)):
        oratori.setdefault(x["item"], []).append(x)
    persone = brevi(c, [x["person"] for xs in oratori.values() for x in xs if x["person"]])
    link = url_sedute(c, [r["sitting"] for r in righe])
    out = []
    for r in righe:
        chi = [persone[x["person"]].model_dump(include={"uri", "name"}) | {"group": (persone[x["person"]].group.short_name if persone[x["person"]].group else None)}
               if x["person"] in persone else {"name": x["speaker_label"]} for x in oratori.get(r["uri"], [])]
        out.append({**{k: r[k] for k in ("uri", "title", "stage", "sitting", "date", "chamber", "body_name", "seat", "number", "status")},
                    "url": url_seduta(r["sitting"], r["status"], r["kind"], link.get(r["sitting"])),
                    "acts": atti.get(r["uri"], []), "speakers": chi[:30], "speakers_total": len(chi)})
    return {"total": totale, "items": out, "more": offset + len(out) < totale}


def conta_sedute(c: psycopg.Connection, chamber: str | None = None, body: str | None = "aula", start: dt.date | None = None,
                 end: dt.date | None = None, by_month: bool = False) -> dict:
    """Quante sedute tenute e quante ore, per ramo (e mese). Le ore vengono dai video della WebTV (inizio e fine di ogni
    video, sospensioni comprese): ci sono solo per la Camera."""
    p = {"ramo": chamber, "org": body, "dal": start, "al": end}
    mese = ", to_char(s.date, 'YYYY-MM') AS mese" if by_month else ""
    righe = c.execute(f"""
        WITH s AS (SELECT s.uri, s.chamber, s.date FROM sitting s
                   WHERE s.status = 'held' AND s.kind <> 'committee_summary' AND (%(ramo)s::text IS NULL OR s.chamber = %(ramo)s)
                     AND (%(org)s::text IS NULL OR (%(org)s = 'aula' AND s.body LIKE '%%:aula') OR s.body = %(org)s)
                     AND (%(dal)s::date IS NULL OR s.date >= %(dal)s) AND (%(al)s::date IS NULL OR s.date <= %(al)s)),
        v AS (SELECT sitting, sum(extract(epoch FROM end_ts - start_ts)) AS secondi FROM video
              WHERE sitting IN (SELECT uri FROM s) AND end_ts > start_ts GROUP BY 1)
        SELECT s.chamber AS ramo{mese}, count(*) AS sedute, count(v.sitting) AS sedute_con_video,
               round(sum(v.secondi)::numeric / 3600, 1) AS ore_da_video
        FROM s LEFT JOIN v ON v.sitting = s.uri GROUP BY 1{', 2' if by_month else ''} ORDER BY 1{', 2' if by_month else ''}""", p).fetchall()
    return {"counted": "Sedute tenute (status held), Aula salvo body diverso; ore = somma della durata dei video della WebTV della "
                       "Camera (sospensioni comprese). Il Senato non ha video nei dati: per il Senato le ore non ci sono.",
            "rows": [dict(r) for r in righe]}
