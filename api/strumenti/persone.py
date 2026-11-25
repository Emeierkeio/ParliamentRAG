"""Parlamentari e membri del governo: ricerca, scheda, composizione dei gruppi alla data."""

from __future__ import annotations

import datetime as dt
import re
import unicodedata

import psycopg

from ..modelli import Composition, Group, GroupCount, Mandate, Membership, Person, PersonBrief, PersonCounts, Post
from .comune import LEGISLATURA, brevi, gruppo, stessa_persona

def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", t.lower())


def cerca_persone(c: psycopg.Connection, q: str | None = None, chamber: str | None = None, group: str | None = None,
                  in_office: bool | None = True, limit: int = 50) -> list[PersonBrief]:
    """Parlamentari della legislatura per nome, ramo e gruppo (uri o sigla; il Misto comprende le sue componenti)."""
    righe = c.execute("""
        SELECT DISTINCT m.person, norm_nome(p.family_name) AS cognome FROM mandate m JOIN person p ON p.uri = m.person
        WHERE m.legislature = %(leg)s
          AND (%(ramo)s::text IS NULL OR m.chamber = %(ramo)s)
          AND (%(q)s::text IS NULL OR norm_nome(concat(p.given_name, p.family_name)) LIKE '%%' || norm_nome(%(q)s) || '%%'
               OR norm_nome(concat(p.family_name, p.given_name)) LIKE '%%' || norm_nome(%(q)s) || '%%')
          AND (%(attivo)s::boolean IS NOT TRUE OR m.end_date IS NULL)""",   # falso o vuoto: anche chi non è più in carica
        {"leg": LEGISLATURA, "ramo": chamber, "q": q, "attivo": in_office}).fetchall()
    persone = list(brevi(c, [r["person"] for r in righe]).values())
    if group:
        g = group.lower()
        persone = [p for p in persone if p.group and g in (p.group.uri.lower(), (p.group.short_name or "").lower(), (p.group.part_of or "").lower())]
    if q:                                              # prima chi ha il cognome che comincia con la parola cercata
        cognomi = {r["person"]: r["cognome"] for r in righe}
        persone.sort(key=lambda p: (not cognomi.get(p.uri, "").startswith(_norm(q)), p.name))
    else:
        persone.sort(key=lambda p: p.name.split()[-1:] + [p.name])
    return persone[:limit]


def scheda_persona(c: psycopg.Connection, uri: str) -> Person | None:
    """La scheda completa: anagrafica, mandati, gruppi, organi, cariche e i conti di interventi, voti e firme.
    Interventi, voti e firme contano tutte le schede della stessa persona (Camera e Senato)."""
    base = brevi(c, [uri]).get(uri)
    if base is None:
        return None
    p = c.execute("SELECT * FROM person WHERE uri = %s", (base.uri,)).fetchone()
    ids = stessa_persona(c, base.uri)
    mandati = [Mandate(**{k: m[k] for k in Mandate.model_fields}) for m in
               c.execute("SELECT * FROM mandate WHERE person = ANY(%s) ORDER BY start_date", (ids,))]
    gruppi = [Membership(group=gruppo(m), role=m["role"], start_date=m["start_date"], end_date=m["end_date"]) for m in c.execute("""
        SELECT m.role, m.start_date, m.end_date, g.uri AS g_uri, name_at(g.uri, m.start_date) AS g_name, g.short_name AS g_short, g.kind AS g_kind, g.part_of AS g_part_of
        FROM membership m JOIN grp g ON g.uri = m.grp WHERE m.person = ANY(%s) ORDER BY m.start_date, g.kind""", (ids,))]
    organi = [Post(target=s["body"], target_name=s["name"], title=s["role"], start_date=s["start_date"], end_date=s["end_date"]) for s in c.execute("""
        SELECT s.body, b.name, s.role, s.start_date, s.end_date FROM seat s JOIN body b ON b.uri = s.body
        WHERE s.person = ANY(%s) ORDER BY s.end_date IS NULL DESC, s.start_date DESC""", (ids,))]
    cariche = [Post(target=o["target"], target_name=o["nome"], title=o["title"], start_date=o["start_date"], end_date=o["end_date"]) for o in c.execute("""
        SELECT o.target, o.title, o.start_date, o.end_date,
               coalesce(b.name, g.name, mi.name, gv.name) AS nome
        FROM office o LEFT JOIN body b ON b.uri = o.target LEFT JOIN grp g ON g.uri = o.target
        LEFT JOIN ministry mi ON mi.uri = o.target LEFT JOIN government gv ON gv.uri = o.target
        WHERE o.person = ANY(%s) ORDER BY o.end_date IS NULL DESC, o.start_date DESC""", (ids,))]
    n = c.execute("""
        SELECT (SELECT count(*) FROM speech WHERE person = ANY(%(ids)s)) AS speeches,
               (SELECT count(*) FROM ballot WHERE person = ANY(%(ids)s)) AS ballots,
               (SELECT count(*) FROM ballot WHERE person = ANY(%(ids)s) AND result IN ('favor', 'against', 'abstain', 'voted')) AS ballots_cast,
               (SELECT count(*) FROM ballot WHERE person = ANY(%(ids)s) AND result = 'mission') AS ballots_mission,
               (SELECT count(*) FROM act_sponsor s JOIN act a ON a.uri = s.act WHERE s.person = ANY(%(ids)s) AND s.first AND a.kind = 'bill') AS bills_first_signer,
               (SELECT count(*) FROM amendment_signer WHERE person = ANY(%(ids)s)) AS amendments_signed""", {"ids": ids}).fetchone()
    return Person(**base.model_dump(), given_name=p["given_name"], family_name=p["family_name"], gender=p["gender"],
                  birth_date=p["birth_date"], birth_place=p["birth_place"], profession=p["profession"], source_uri=p["source_uri"],
                  same_as=[i for i in ids if i != base.uri], mandates=mandati, memberships=gruppi, bodies=organi, offices=cariche,
                  counts=PersonCounts(**n))


def composizione(c: psycopg.Connection, chamber: str, d: dt.date | None = None) -> Composition:
    """I gruppi alla data con il numero di membri; il Misto diviso per componente."""
    d = d or dt.date.today()
    righe = c.execute("""
        SELECT m.person, g.uri AS g_uri, g.name AS g_name, g.short_name AS g_short, g.kind AS g_kind, g.part_of AS g_part_of
        FROM mandate m LEFT JOIN grp g ON g.uri = group_at(m.person, %(d)s)
        WHERE m.legislature = %(leg)s AND m.chamber = %(ramo)s AND m.start_date <= %(d)s AND (m.end_date IS NULL OR m.end_date >= %(d)s)""",
        {"d": d, "leg": LEGISLATURA, "ramo": chamber}).fetchall()
    conti: dict[str, GroupCount] = {}
    componenti: dict[str, dict[str, GroupCount]] = {}
    senza = 0
    for r in righe:
        g = gruppo(r)
        if g is None:
            senza += 1
            continue
        if g.kind == "misto_component" and g.part_of:
            misto = conti.get(g.part_of) or GroupCount(group=_gruppo_per_uri(c, g.part_of), members=0)
            conti[g.part_of] = misto
            misto.members += 1
            componenti.setdefault(g.part_of, {}).setdefault(g.uri, GroupCount(group=g, members=0)).members += 1
        else:
            conti.setdefault(g.uri, GroupCount(group=g, members=0)).members += 1
    for u, cs in componenti.items():
        conti[u].components = sorted(cs.values(), key=lambda x: -x.members)
    return Composition(chamber=chamber, date=d, members=len(righe), in_groups=len(righe) - senza,
                       groups=sorted(conti.values(), key=lambda x: -x.members), not_in_group=senza)


def _livello_studio(t: str | None) -> str:
    if not t or not t.strip():
        return "non indicato"
    x = t.strip().lower()
    if x.startswith(("laurea", "dottorato", "master", "phd", "ingegnere", "ricercat", "professor")):
        return "laurea o titolo superiore"
    if x.startswith(("diploma", "perito", "licenza", "maturit")):
        return "diploma o licenza"
    return "altro"


def profilo_parlamentari(c: psycopg.Connection, chamber: str, group: str | None = None, d: dt.date | None = None,
                         limit: int = 30, q: str | None = None) -> dict:
    """Titolo di studio e professione dei parlamentari in carica alla data, dalle schede ufficiali; con `group` solo
    quel gruppo (sigla, nome o uri, il Misto comprende le sue componenti)."""
    d = d or dt.date.today()
    righe = c.execute("""
        SELECT p.education, p.profession, g.uri AS g_uri, g.short_name AS g_short, g.name AS g_name, g.part_of AS g_part_of
        FROM mandate m JOIN person p ON p.uri = m.person LEFT JOIN grp g ON g.uri = group_at(m.person, %(d)s)
        WHERE m.legislature = %(leg)s AND m.chamber = %(ramo)s AND m.start_date <= %(d)s AND (m.end_date IS NULL OR m.end_date >= %(d)s)""",
        {"d": d, "leg": LEGISLATURA, "ramo": chamber}).fetchall()
    if group:
        q = group.strip().lower()
        righe = [r for r in righe if q in {(r["g_uri"] or "").lower(), (r["g_short"] or "").lower(), (r["g_name"] or "").lower(),
                                            (r["g_part_of"] or "").lower()}]
    livelli: dict[str, int] = {}
    titoli: dict[str, int] = {}
    professioni: dict[str, int] = {}
    for r in righe:
        livelli[_livello_studio(r["education"])] = livelli.get(_livello_studio(r["education"]), 0) + 1
        if r["education"] and r["education"].strip():
            t = r["education"].strip()
            t = t[:1].upper() + t[1:].lower()
            titoli[t] = titoli.get(t, 0) + 1
        if r["profession"] and r["profession"].strip():
            t = r["profession"].strip().lower()
            professioni[t] = professioni.get(t, 0) + 1
    ordina = lambda x: [{"value": k, "members": n} for k, n in sorted(x.items(), key=lambda kv: (-kv[1], kv[0]))][:limit]  # noqa: E731
    nota = ("Titolo di studio e professione come li scrive la scheda ufficiale di ogni parlamentare in carica alla data; "
            "«non indicato» = la scheda non lo dice, quindi i conti sono un minimo. Il livello è ricavato dalle prime parole del "
            "titolo (Laurea, Dottorato, Master → laurea o titolo superiore; Diploma, Licenza → diploma o licenza).")
    if chamber == "senato":
        nota += " Le schede del Senato non riportano il titolo di studio: per il Senato c'è solo la professione."
    cerca = None
    if q and q.strip():
        t = _norm(q)
        trovati = [r for r in righe if t in _norm(r["profession"] or "") or t in _norm(r["education"] or "")]
        cerca = {"q": q, "members": len(trovati), "note": "parlamentari la cui professione o il cui titolo di studio contiene la parola "
                 "(«avvocat» trova avvocato, avvocata, avvocato e docente…): è un minimo, alcune schede non lo dicono"}
    return {"chamber": chamber, "date": d, "group": group, "members": len(righe), "counted": nota, "match": cerca,
            "education_level": livelli if chamber != "senato" else None,
            "education": ordina(titoli) if chamber != "senato" else None,
            "profession": ordina(professioni),
            "profession_not_given": sum(1 for r in righe if not (r["profession"] or "").strip())}


def _gruppo_per_uri(c: psycopg.Connection, uri: str) -> Group:
    g = c.execute("SELECT uri, name, short_name, kind, part_of FROM grp WHERE uri = %s", (uri,)).fetchone()
    return Group(**g)


ORGANI_DI_SOLITO = ("standing_committee",)


def organo(c: psycopg.Connection, q: str | None = None, chamber: str | None = None, d: dt.date | None = None,
           titles: list[str] | None = None) -> dict:
    """Gli organi (commissioni, giunte, comitati, delegazioni) per nome o uri, con le cariche alla data (presidente,
    vicepresidenti, segretari…), il gruppo di ognuno alla stessa data e il numero dei membri. Senza `q`, le commissioni
    permanenti del ramo, con presidente e vicepresidenti."""
    d = d or dt.date.today()
    righe = c.execute("""
        SELECT uri, chamber, kind, name, start_date, end_date FROM body
        WHERE legislature = %(leg)s AND (%(ramo)s::text IS NULL OR chamber = %(ramo)s)
          AND (start_date IS NULL OR start_date <= %(d)s) AND (end_date IS NULL OR end_date >= %(d)s)
        ORDER BY chamber, name""", {"leg": LEGISLATURA, "ramo": chamber, "d": d}).fetchall()
    if q:
        t = q.strip().lower()
        livelli = [[r for r in righe if t == r["uri"].lower() or t == r["name"].lower()],
                   [r for r in righe if r["name"].lower().startswith(t + " ") or r["name"].lower().startswith(t + "ª")],
                   [r for r in righe if _norm(q) in _norm(r["name"])]]
        righe = next((x for x in livelli if x), [])
    else:
        righe = [r for r in righe if r["kind"] in ORGANI_DI_SOLITO]
        titles = titles or ["chair", "vice_chair"]
    righe = righe[:30]
    uris = [r["uri"] for r in righe]
    cariche = c.execute("""
        SELECT o.target, o.person, o.title, o.title_raw, o.start_date FROM office o
        WHERE o.target = ANY(%(u)s) AND o.start_date <= %(d)s AND (o.end_date IS NULL OR o.end_date >= %(d)s)
          AND (%(titoli)s::text[] IS NULL OR o.title = ANY(%(titoli)s))
        ORDER BY o.target, array_position(ARRAY['chair', 'vice_chair', 'secretary'], o.title) NULLS LAST, o.start_date""",
                        {"u": uris, "d": d, "titoli": titles}).fetchall()
    membri = {r["body"]: r["n"] for r in c.execute("""SELECT body, count(DISTINCT person) AS n FROM seat WHERE body = ANY(%(u)s)
                                                      AND start_date <= %(d)s AND (end_date IS NULL OR end_date >= %(d)s) GROUP BY 1""",
                                                   {"u": uris, "d": d})}
    persone = brevi(c, [x["person"] for x in cariche], d)
    per_organo: dict[str, list[dict]] = {}
    for x in cariche:
        p = persone.get(x["person"])
        per_organo.setdefault(x["target"], []).append(
            {"title": x["title_raw"] or x["title"], "since": x["start_date"], "person": p.name if p else x["person"], "uri": x["person"],
             "group": (p.group.short_name or p.group.name) if p and p.group else None})
    return {"date": d, "counted": "Cariche in corso alla data (office), con il gruppo di ognuno alla stessa data, il Misto per componente; "
                                  "members = persone con un seggio nell'organo alla data. Camera: le commissioni permanenti si chiamano "
                                  "«I Commissione» … «XIV Commissione»; Senato: «1ª Commissione permanente (…)» … «10ª Commissione permanente (…)».",
            "total": len(righe),
            "items": [{"uri": r["uri"], "chamber": r["chamber"], "kind": r["kind"], "name": r["name"], "members": membri.get(r["uri"]),
                       "offices": per_organo.get(r["uri"], [])} for r in righe]}
