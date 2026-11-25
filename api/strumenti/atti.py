"""Atti: progetti di legge, sindacato ispettivo e indirizzo, atti del Governo e nomine sottoposti a parere, con firmatari,
commissioni a cui sono assegnati (con termine e parere), relatori, iter, testi, votazioni ed emendamenti."""

from __future__ import annotations

import re

import psycopg

from ..modelli import Act, ActBrief, ActRef, Amendment, AmendmentCounts, Assignment, Rapporteur, Signer, Sponsor, Step, TextVersion
from .comune import LEGISLATURA, brevi, parametri_soprannomi, stessa_persona
from .conti import INIZIATIVE, SQL_INIZIATIVA
from .voti import SQL_VOTO_BREVE, voto_breve

CAMPI_BREVI = "a.uri, a.chamber, a.legislature, a.number, a.kind, a.title, a.date, a.status, a.law_number, a.card_url, a.initiative"
# le espressioni sono quelle degli indici act_fts e act_text_fts: se cambiano, Postgres legge tutta la tabella
SQL_Q_TITOLO = "to_tsvector('italian', coalesce(a.title, '')) @@ websearch_to_tsquery('italian', %(q)s)"
SQL_Q_TESTO = "to_tsvector('italian', coalesce(a.text, '')) @@ websearch_to_tsquery('italian', %(q)s)"
SQL_SOPRANNOME = "(a.uri = ANY(%(sopr)s::text[]) OR a.title ~ %(sopr_tit)s::text)"      # soprannomi.py

# «AC 1695», «A.C. 1695», «C. 1917-B», «S. 1353», «A.S. 1689/I», «ddl S. 1353», «pdl n. 1695»: il numero e, se c'è, il ramo
NUMERO = re.compile(r"""^\s*(?:(?:ddl|pdl|d\.d\.l\.|p\.d\.l\.)\s*)?
                        (?:(?P<ramo>A\.?\s*[CS]\.?|[CS]\.|[CS](?=\s*\d))\s*)?
                        (?:n\.\s*)?(?P<num>\d.*)$""", re.I | re.X)  # su un testo già senza spazi ai bordi
OGGETTO = 320                                           # caratteri dell'oggetto negli elenchi
# dove comincia la parte che dice l'argomento: i destinatari di un'interrogazione, l'aula di una mozione o di un odg
INIZIO_OGGETTO = re.compile(r"\b[Aa](?:l|i|lla|gli) (?:Ministr|Presidente|Vice)|\b(?:I|Il|La|Le) sottoscritt|"
                            r"\b(?:La Camera|Il Senato)\b|(?:\bLa |\bLe |\bL')(?:[IVXL]+|\d+[ªa])? ?Commission[ei]\b")


def numero_e_ramo(numero: str) -> tuple[str, str | None]:
    """Il numero dell'atto senza i prefissi che si usano in aula e sui giornali, e il ramo che indicano (None se nessuno)."""
    numero = (numero or "").strip()[:60]
    m = NUMERO.match(numero)
    if not m:
        return numero, None
    ramo = m["ramo"]
    return m["num"], ({"C": "camera", "S": "senato"}[re.sub(r"[^CS]", "", ramo.upper())[-1]] if ramo else None)


def oggetto(testo: str | None) -> str | None:
    """Di un atto di sindacato ispettivo o di indirizzo: a chi è rivolto e le prime righe, senza l'intestazione e i firmatari."""
    if not testo:
        return None
    t = re.sub(r"\s+", " ", testo).strip()
    m = INIZIO_OGGETTO.search(t)
    if m:
        t = t[m.start():]
    else:
        t = re.split(r"seduta n\.\s*\d+\s*", t, maxsplit=1)[-1]
    t = re.sub(r"\s+\.\s+(—|-)", r" \1", t)            # «sociali . — Per sapere» -> «sociali — Per sapere»
    return t if len(t) <= OGGETTO else t[:OGGETTO].rsplit(" ", 1)[0] + "…"


def ha_pareri(c: psycopg.Connection) -> bool:
    """Le colonne del parere in act_assignment nascono con lo schema nuovo: finché non c'è, la scheda dell'atto e l'agenda
    restano come prima invece di rompersi (un servizio rilasciato prima dello schema)."""
    return bool(c.execute("""SELECT EXISTS (SELECT 1 FROM information_schema.columns
                             WHERE table_schema = 'public' AND table_name = 'act_assignment' AND column_name = 'deadline') AS c""").fetchone()["c"])


def cerca_atti(c: psycopg.Connection, q: str | None = None, chamber: str | None = None, kind: str | None = None,
               number: str | None = None, signer: str | None = None, limit: int = 50, offset: int = 0,
               initiative: str | None = None) -> tuple[int, list[ActBrief]]:
    """Atti per parole del titolo o del testo (ricerca in italiano), ramo, tipo, numero, firmatario (uri) o iniziativa,
    dal più recente; con `q` prima gli atti che hanno le parole nel titolo. Il testo serve per il sindacato ispettivo, il
    cui titolo è solo l'intestazione («INTERROGAZIONE A RISPOSTA SCRITTA 4/09302 presentata da…»).
    `initiative`: una categoria (governo, parlamentare, regione, cnel, popolare, mista) o parole del presentatore
    come le scrive la fonte («Regione Toscana», «Consiglio regionale»)."""
    firmatari = stessa_persona(c, signer) if signer else None
    if number:
        number, ramo = numero_e_ramo(number)
        chamber = chamber or ramo
    ini = initiative.strip().lower() if initiative else None
    categoria, testo = (ini, None) if ini in INIZIATIVE else (None, initiative)
    filtro = f"""a.legislature = %(leg)s AND (%(ramo)s::text IS NULL OR a.chamber = %(ramo)s) AND (%(tipo)s::text IS NULL OR a.kind = %(tipo)s)
        AND (%(num)s::text IS NULL OR a.number = %(num)s OR replace(a.number, '/', '-') = %(num)s)
        AND (%(q)s::text IS NULL OR {SQL_Q_TITOLO} OR {SQL_Q_TESTO} OR {SQL_SOPRANNOME})
        AND (%(firm)s::text[] IS NULL OR EXISTS (SELECT 1 FROM act_sponsor s WHERE s.act = a.uri AND s.person = ANY(%(firm)s)))
        AND (%(ini)s::text IS NULL OR ({SQL_INIZIATIVA}) = %(ini)s)
        AND (%(ini_testo)s::text IS NULL OR a.initiative ILIKE '%%' || %(ini_testo)s || '%%')"""
    p = {"leg": LEGISLATURA, "ramo": chamber, "tipo": kind, "num": number, "q": q, "firm": firmatari, "lim": limit, "off": offset,
         "ini": categoria, "ini_testo": testo, **parametri_soprannomi(q)}
    totale = c.execute(f"SELECT count(*) AS n FROM act a WHERE {filtro}", p).fetchone()["n"]
    # prima gli atti del soprannome («premierato»), poi quelli con le parole nel titolo, poi il resto dal più recente
    titolo_prima = f"coalesce({SQL_SOPRANNOME}, false) DESC, ({SQL_Q_TITOLO}) DESC, " if q else ""
    # con q, il passaggio del testo dove compaiono le parole: fra tanti atti con lo stesso titolo è quello che li distingue
    passaggio = (f"CASE WHEN {SQL_Q_TESTO} THEN ts_headline('italian', a.text, websearch_to_tsquery('italian', %(q)s), "
                 "'StartSel=\"\", StopSel=\"\", MaxWords=35, MinWords=15, MaxFragments=1') END" if q else "NULL::text")
    righe = c.execute(f"""SELECT {CAMPI_BREVI}, a.text AS testo, {passaggio} AS excerpt FROM act a WHERE {filtro}
                          ORDER BY {titolo_prima}a.date DESC NULLS LAST, a.uri LIMIT %(lim)s OFFSET %(off)s""", p)
    return totale, [ActBrief(**{k: v for k, v in r.items() if k != "testo"}, subject=oggetto(r["testo"])) for r in righe]


def atto(c: psycopg.Connection, uri: str) -> Act | None:
    a = c.execute("SELECT * FROM act WHERE uri = %s", (uri,)).fetchone()
    if not a:
        return None
    firme = c.execute("SELECT person, first, as_office FROM act_sponsor WHERE act = %s", (uri,)).fetchall()
    persone = brevi(c, [f["person"] for f in firme], a["date"])
    firmatari = sorted((Sponsor(person=persone[f["person"]], first=f["first"], as_office=f["as_office"]) for f in firme if f["person"] in persone),
                       key=lambda s: (not s.first, s.person.name))
    # commissioni: prima quella di merito (o del parere), poi le altre per data
    parere = "x.deadline, x.basis, x.opinion, x.opinion_date" if ha_pareri(c) else "NULL::date AS deadline"
    assegnazioni = [Assignment(**r) for r in c.execute(f"""
        SELECT b.uri AS body, coalesce(x.title, b.name, x.body) AS body_name, x.seat, x.date, {parere}
        FROM act_assignment x LEFT JOIN body b ON b.uri = x.body WHERE x.act = %s
        ORDER BY (x.seat IN ('referente', 'redigente', 'deliberante', 'opinion')) DESC, x.date NULLS LAST, 2""", (uri,))]
    rel = c.execute("SELECT name_raw, role, person FROM act_rapporteur WHERE act = %s ORDER BY (role = 'minority'), name_raw", (uri,)).fetchall()
    schede = brevi(c, [r["person"] for r in rel if r["person"]], a["date"])
    relatori = [Rapporteur(name=r["name_raw"], role=r["role"], person=schede.get(r["person"])) for r in rel]
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
    return Act(**{k: a[k] for k in Act.model_fields if k in a and a[k] is not None}, sponsors=firmatari, assignments=assegnazioni,
               rapporteurs=relatori, steps=passi, versions=versioni, joined=abbinati, votes=voti,
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
        # gli articoli di un decreto dentro la legge di conversione non hanno il numero: si cerca «Art. N.» nel testo
        testo = c.execute("SELECT text FROM act_text WHERE code = %s", (code,)).fetchone()["text"]
        m = re.search(rf"(?m)^\s*Art(?:icolo|\.)\s*{re.escape(n)}\.?\s*$(.*?)(?=^\s*Art(?:icolo|\.)\s*\d+[-\w]*\.?\s*$|\Z)",
                      testo, re.S | re.I)
        if m:
            return {"code": code, "kind": t["kind"], "number": n, "text": f"Art. {n}.{m.group(1)}".strip()[:20000]}
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
