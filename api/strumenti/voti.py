"""Votazioni elettroniche: elenco, esito, voto dei gruppi (il Misto per componente) e dei singoli."""

from __future__ import annotations

import datetime as dt

import psycopg

from ..modelli import ActRef, Ballot, Group, GroupVote, Vote, VoteBrief
from .comune import brevi

SQL_VOTO_BREVE = """SELECT v.uri, v.sitting, v.chamber, v.number, v.date, v.title, v.kind, v.favor, v.against, v.abstain,
                           v.approved, v.secret, v.confidence, v.source_url FROM vote v"""
SCELTE = ("favor", "against", "abstain")


def voto_breve(r: dict) -> VoteBrief:
    return VoteBrief(**r)


def elenco_votazioni(c: psycopg.Connection, chamber: str | None = None, act: str | None = None, kind: str | None = None,
                     start: dt.date | None = None, end: dt.date | None = None, final: bool | None = None,
                     limit: int = 50, offset: int = 0, confidence: bool | None = None) -> tuple[int, list[VoteBrief]]:
    """Votazioni dalla più recente; `act` è l'uri dell'atto votato. Alla Camera la fiducia si vota sugli articoli
    (kind article, confidence vero): `kind="confidence"` vale come `confidence=True`, così vale per tutti e due i rami."""
    if kind == "confidence":
        kind, confidence = None, True
    filtro = """(%(ramo)s::text IS NULL OR v.chamber = %(ramo)s) AND (%(tipo)s::text IS NULL OR v.kind = %(tipo)s)
        AND (%(fiducia)s::boolean IS NULL OR coalesce(v.confidence, false) = %(fiducia)s)
        AND (%(dal)s::date IS NULL OR v.date >= %(dal)s) AND (%(al)s::date IS NULL OR v.date <= %(al)s)
        AND (%(finale)s::boolean IS NULL OR v.final = %(finale)s)
        AND (%(atto)s::text IS NULL OR EXISTS (SELECT 1 FROM vote_act x WHERE x.vote = v.uri AND x.act = %(atto)s))"""
    p = {"ramo": chamber, "tipo": kind, "dal": start, "al": end, "finale": final, "atto": act, "fiducia": confidence,
         "lim": limit, "off": offset}
    totale = c.execute(f"SELECT count(*) AS n FROM vote v WHERE {filtro}", p).fetchone()["n"]
    righe = c.execute(f"{SQL_VOTO_BREVE} WHERE {filtro} ORDER BY v.date DESC, v.number DESC LIMIT %(lim)s OFFSET %(off)s", p).fetchall()
    # il titolo dell'atto votato: quello del voto dice spesso solo il numero («Articolo 1 PDL n. 2822-B»)
    titoli = {r["vote"]: r["title"] for r in c.execute(
        """SELECT DISTINCT ON (x.vote) x.vote, left(a.title, 200) AS title FROM vote_act x JOIN act a ON a.uri = x.act
           WHERE x.vote = ANY(%s) ORDER BY x.vote, x.act_ref""", ([r["uri"] for r in righe],))}
    return totale, [voto_breve({**r, "act_title": titoli.get(r["uri"])}) for r in righe]


def votazione(c: psycopg.Connection, uri: str, with_ballots: bool = True) -> Vote | None:
    v = c.execute("SELECT * FROM vote WHERE uri = %s", (uri,)).fetchone()
    if not v:
        return None
    atti = [ActRef(ref=a["act_ref"], uri=a["act"], title=a["title"]) for a in c.execute(
        "SELECT x.act_ref, x.act, a.title FROM vote_act x LEFT JOIN act a ON a.uri = x.act WHERE x.vote = %s ORDER BY x.act_ref", (uri,))]
    # il gruppo scritto nel voto; se l'anagrafica non lo conosce, il gruppo a cui è legato in grp_alias (versioni di un
    # gruppo dopo un cambio di nome) o, se manca anche lì, il gruppo della persona alla data
    schede = c.execute("""SELECT b.person, b.result, g.uri AS grp, g.name, g.short_name, g.kind, g.part_of
                          FROM ballot b JOIN vote v ON v.uri = b.vote
                          LEFT JOIN grp g ON g.uri = coalesce((SELECT uri FROM grp WHERE uri = b.grp), (SELECT grp FROM grp_alias WHERE alias = b.grp),
                                                                group_at(b.person, v.date))
                          WHERE b.vote = %s""", (uri,)).fetchall()
    gruppi: dict[str | None, GroupVote] = {}
    for b in schede:
        gv = gruppi.get(b["grp"])
        if gv is None:
            # nel Misto senza componente: i non iscritti, da dire così (il Misto si legge per componente)
            ni = (b["name"] or "").strip().lower() == "misto" and b["kind"] != "misto_component"
            g = Group(uri=b["grp"], name="Misto, non iscritti" if ni else b["name"] or b["grp"], short_name=b["short_name"],
                      kind=b["kind"] or "group", part_of=b["part_of"]) if b["grp"] else None
            gv = gruppi[b["grp"]] = GroupVote(group=g)
        campo = b["result"] if b["result"] in ("favor", "against", "abstain", "absent", "mission") else "other"
        setattr(gv, campo, getattr(gv, campo) + 1)
    for gv in gruppi.values():
        conti = {s: getattr(gv, s) for s in SCELTE}
        gv.majority = max(conti, key=conti.get) if any(conti.values()) else None
    persone = brevi(c, [b["person"] for b in schede], v["date"]) if with_ballots else {}
    voti = [Ballot(person=persone[b["person"]], result=b["result"]) for b in schede if b["person"] in persone]
    voti.sort(key=lambda x: (x.result, x.person.name))
    return Vote(**{k: v[k] for k in Vote.model_fields if k in v}, acts=atti,
                groups=sorted(gruppi.values(), key=lambda g: -(g.favor + g.against + g.abstain + g.absent + g.mission + g.other)),
                ballots=voti)
