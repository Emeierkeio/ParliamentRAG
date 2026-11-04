"""Atti: progetti di legge, sindacato ispettivo e indirizzo, con firmatari, iter, testi, votazioni ed emendamenti."""

from __future__ import annotations

import psycopg

from ..modelli import Act, ActBrief, ActRef, Amendment, AmendmentCounts, Signer, Sponsor, Step, TextVersion
from .comune import LEGISLATURA, brevi, stessa_persona
from .conti import INIZIATIVE, SQL_INIZIATIVA
from .voti import SQL_VOTO_BREVE, voto_breve

CAMPI_BREVI = "a.uri, a.chamber, a.legislature, a.number, a.kind, a.title, a.date, a.status, a.law_number, a.card_url, a.initiative"


def cerca_atti(c: psycopg.Connection, q: str | None = None, chamber: str | None = None, kind: str | None = None,
               number: str | None = None, signer: str | None = None, limit: int = 50, offset: int = 0,
               initiative: str | None = None) -> tuple[int, list[ActBrief]]:
    """Atti per parole del titolo (ricerca in italiano), ramo, tipo, numero, firmatario (uri) o iniziativa, dal più
    recente. `initiative`: una categoria (governo, parlamentare, regione, cnel, popolare, mista) o parole del presentatore
    come le scrive la fonte («Regione Toscana», «Consiglio regionale»)."""
    firmatari = stessa_persona(c, signer) if signer else None
    ini = initiative.strip().lower() if initiative else None
    categoria, testo = (ini, None) if ini in INIZIATIVE else (None, initiative)
    filtro = f"""a.legislature = %(leg)s AND (%(ramo)s::text IS NULL OR a.chamber = %(ramo)s) AND (%(tipo)s::text IS NULL OR a.kind = %(tipo)s)
        AND (%(num)s::text IS NULL OR a.number = %(num)s OR replace(a.number, '/', '-') = %(num)s)
        AND (%(q)s::text IS NULL OR to_tsvector('italian', coalesce(a.title, '')) @@ websearch_to_tsquery('italian', %(q)s))
        AND (%(firm)s::text[] IS NULL OR EXISTS (SELECT 1 FROM act_sponsor s WHERE s.act = a.uri AND s.person = ANY(%(firm)s)))
        AND (%(ini)s::text IS NULL OR ({SQL_INIZIATIVA}) = %(ini)s)
        AND (%(ini_testo)s::text IS NULL OR a.initiative ILIKE '%%' || %(ini_testo)s || '%%')"""
    p = {"leg": LEGISLATURA, "ramo": chamber, "tipo": kind, "num": number, "q": q, "firm": firmatari, "lim": limit, "off": offset,
         "ini": categoria, "ini_testo": testo}
    totale = c.execute(f"SELECT count(*) AS n FROM act a WHERE {filtro}", p).fetchone()["n"]
    righe = c.execute(f"SELECT {CAMPI_BREVI} FROM act a WHERE {filtro} ORDER BY a.date DESC NULLS LAST, a.uri LIMIT %(lim)s OFFSET %(off)s", p)
    return totale, [ActBrief(**r) for r in righe]


def atto(c: psycopg.Connection, uri: str) -> Act | None:
    a = c.execute("SELECT * FROM act WHERE uri = %s", (uri,)).fetchone()
    if not a:
        return None
    firme = c.execute("SELECT person, first, as_office FROM act_sponsor WHERE act = %s", (uri,)).fetchall()
    persone = brevi(c, [f["person"] for f in firme], a["date"])
    firmatari = sorted((Sponsor(person=persone[f["person"]], first=f["first"], as_office=f["as_office"]) for f in firme if f["person"] in persone),
                       key=lambda s: (not s.first, s.person.name))
    passi = [Step(order=s["ord"], title=s["title"], date=s["date"]) for s in c.execute("SELECT ord, title, date FROM act_step WHERE act = %s ORDER BY ord", (uri,))]
    # i testi: alla Camera dalle versioni dell'atto (act_version_text), al Senato dalla colonna act di act_text
    versioni = [TextVersion(**r) for r in c.execute("""
        SELECT t.code, t.kind, v.title, v.date, (SELECT count(*) FROM act_article x WHERE x.code = t.code) AS articles, length(t.text) AS length
        FROM act_text t LEFT JOIN act_version v ON v.act = %(u)s AND v.uri LIKE '%%:vta%%\\_' || t.code
        WHERE t.act = %(u)s OR v.uri IS NOT NULL ORDER BY v.date NULLS LAST, t.code""", {"u": uri})]
    abbinati = [ActRef(ref=j["main_act"], uri=j["main_act"], title=j["title"]) for j in c.execute(
        "SELECT j.main_act, m.title FROM act_joint j LEFT JOIN act m ON m.uri = j.main_act WHERE j.act = %s", (uri,))]
    voti = [voto_breve(v) for v in c.execute(SQL_VOTO_BREVE + " JOIN vote_act x ON x.vote = v.uri WHERE x.act = %s ORDER BY v.date, v.number", (uri,))]
    esiti = c.execute("SELECT coalesce(outcome, 'non indicato') AS esito, count(*) AS n FROM amendment WHERE act = %s GROUP BY 1", (uri,)).fetchall()
    return Act(**{k: a[k] for k in Act.model_fields if k in a}, sponsors=firmatari, steps=passi, versions=versioni, joined=abbinati, votes=voti,
               amendments=AmendmentCounts(total=sum(e["n"] for e in esiti), by_outcome={e["esito"]: e["n"] for e in esiti}))


def articolo(c: psycopg.Connection, code: str, number: str | None = None) -> dict | None:
    """Il testo di un articolo di una versione dell'atto (il codice viene da `atto`, campo versions); senza numero
    l'elenco degli articoli con le prime parole."""
    t = c.execute("SELECT code, kind, length(text) AS length FROM act_text WHERE code = %s", (code,)).fetchone()
    if not t:
        return None
    righe = c.execute("SELECT ord, number, text FROM act_article WHERE code = %s ORDER BY ord", (code,)).fetchall()
    if number is None:
        return {"code": code, "kind": t["kind"], "articles": [{"number": r["number"], "start": (r["text"] or "")[:160]} for r in righe]}
    n = number.strip().lower().removeprefix("art.").removeprefix("articolo").strip()
    scelti = [r for r in righe if (r["number"] or "").strip().lower().removeprefix("art.").strip() == n]
    if not scelti:
        return {"code": code, "error": f"nessun articolo {number}: ci sono {', '.join(r['number'] or '?' for r in righe[:60])}"}
    return {"code": code, "kind": t["kind"], "number": scelti[0]["number"], "text": scelti[0]["text"]}


def emendamenti(c: psycopg.Connection, act: str, signer: str | None = None, group: str | None = None, outcome: str | None = None,
                venue: str | None = None, q: str | None = None, limit: int = 50, offset: int = 0) -> tuple[int, list[Amendment]]:
    """Emendamenti di un atto, filtrati per firmatario (uri), gruppo del firmatario alla data, esito, sede e parole del testo."""
    firmatari = stessa_persona(c, signer) if signer else None
    filtro = """e.act = %(atto)s AND (%(esito)s::text IS NULL OR e.outcome = %(esito)s) AND (%(sede)s::text IS NULL OR e.venue = %(sede)s)
        AND (%(firm)s::text[] IS NULL OR EXISTS (SELECT 1 FROM amendment_signer s WHERE s.amendment = e.uri AND s.person = ANY(%(firm)s)))
        AND (%(gruppo)s::text IS NULL OR EXISTS (
              SELECT 1 FROM amendment_signer s JOIN grp g ON g.uri = group_at(s.person, coalesce(e.presented, e.sitting_date, current_date))
              WHERE s.amendment = e.uri AND %(gruppo)s IN (g.uri, g.short_name, g.part_of)))
        AND (%(q)s::text IS NULL OR to_tsvector('italian', coalesce(e.text, '')) @@ websearch_to_tsquery('italian', %(q)s))"""
    p = {"atto": act, "esito": outcome, "sede": venue, "firm": firmatari, "gruppo": group, "q": q, "lim": limit, "off": offset}
    totale = c.execute(f"SELECT count(*) AS n FROM amendment e WHERE {filtro}", p).fetchone()["n"]
    righe = c.execute(f"""SELECT e.uri, e.act, e.number, e.venue, e.article, e.outcome, e.presented, e.sitting_date, e.text
                          FROM amendment e WHERE {filtro} ORDER BY e.venue, e.uri LIMIT %(lim)s OFFSET %(off)s""", p).fetchall()
    firme = c.execute("""SELECT amendment, ord, person, first, concat_ws(' ', given_raw, family_raw) AS nome
                         FROM amendment_signer WHERE amendment = ANY(%s) ORDER BY amendment, ord""", ([r["uri"] for r in righe],)).fetchall()
    persone = brevi(c, [f["person"] for f in firme])
    per_em: dict[str, list[Signer]] = {}
    for f in firme:
        per_em.setdefault(f["amendment"], []).append(Signer(person=persone.get(f["person"]), name_raw=f["nome"] or None, first=f["first"]))
    return totale, [Amendment(**r, signers=per_em.get(r["uri"], [])) for r in righe]
