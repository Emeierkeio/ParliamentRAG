"""Conteggi per numeri, classifiche e matrici: votazioni, voto dei gruppi, presenze, interventi, reazioni del resoconto,
atti, emendamenti e cambi di gruppo. Ogni risultato porta `counted`, che dice esattamente che cosa si è contato (filtri,
periodo, fonte, regole), così la risposta lo può riportare. I due rami non si sommano se non è chiesto (`sum_chambers`):
senza un ramo il conteggio si divide per ramo. Il gruppo è quello alla data, il Misto per componente. Ogni conteggio ha
un tempo massimo (TEMPO) e le righe restituite un tetto (RIGHE_MAX), con il totale delle righe e l'offset per le
successive."""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from contextlib import contextmanager
from itertools import combinations

import psycopg

from .comune import LEGISLATURA, brevi, stessa_persona

TEMPO = 25                        # secondi per query: i conti su tutta la legislatura leggono milioni di schede
RIGHE_MAX = 200
MIN_VOTI_ACCORDO = 20             # sotto, l'accordo fra due gruppi non si mostra
MEMORIA = "64MB"                  # work_mem delle query di conteggio
SCELTE = ("favor", "against", "abstain")
# la categoria dell'iniziativa: alla Camera la fonte la dà già («Governo», «Regioni»), al Senato è testo libero
# («Gov. Meloni-I: …», «Sen. Rossi Mario ed altri», «Regione Toscana», «C.N.E.L.»)
INIZIATIVE = ("governo", "parlamentare", "regione", "cnel", "popolare", "mista")
SQL_INIZIATIVA = """CASE WHEN a.initiative IS NULL THEN NULL
  WHEN a.initiative ~* '^(governo|gov\\.|pres\\. consiglio|presidente del consiglio|ministro|vice ?ministro)' THEN 'governo'
  WHEN a.initiative ~* '^(parlamentare|sen\\.|dep\\.|on\\.)' THEN 'parlamentare'
  WHEN a.initiative ~* '^(regioni|regione|consiglio regionale|provincia autonoma)' THEN 'regione'
  WHEN a.initiative ~* '^(cnel|c\\.n\\.e\\.l)' THEN 'cnel'
  WHEN a.initiative ~* '^popolare' THEN 'popolare'
  WHEN a.initiative ~* '^mist' THEN 'mista'
  ELSE 'altro' END"""
# chi parla: presidenza, governo, relatore, parlamentare, altro (auditi, esperti). Alla Camera i membri del governo non
# hanno as_office: si riconoscono dall'incarico di governo alla data
SQL_RUOLO = """CASE WHEN s.as_office = 'PRESIDENTE' THEN 'presidenza'
  WHEN s.as_office ~* '^relat' THEN 'relatore'
  WHEN s.as_group IS NOT NULL OR s.as_office = 'senatore' THEN 'parlamentare'
  WHEN s.as_office ~* '^(ministr|vice ?ministr|sottosegretari|presidente del consiglio|vice ?presidente del consiglio)'
    OR EXISTS (SELECT 1 FROM office o WHERE o.person = s.person AND o.target LIKE 'it:gov:%%' AND o.start_date <= st.date
               AND (o.end_date IS NULL OR o.end_date >= st.date)) THEN 'governo'
  WHEN s.person IS NOT NULL AND group_at(s.person, st.date) IS NOT NULL THEN 'parlamentare'
  ELSE 'altro' END"""
SQL_GRUPPO_ORATORE = f"CASE WHEN ({SQL_RUOLO}) = 'parlamentare' THEN group_at(s.person, st.date) END"
# il gruppo nel voto: quello scritto nella scheda, la versione del gruppo in grp_alias o il gruppo della persona alla
# data; il Misto si divide per componente con il gruppo alla data (al Senato la scheda dà solo il Misto)
SQL_GRUPPO_VOTO = """CASE WHEN x.g IN (SELECT part_of FROM grp WHERE kind = 'misto_component')
  THEN coalesce((SELECT k.uri FROM grp k WHERE k.uri = group_at(b.person, v.date) AND k.part_of = x.g), x.g) ELSE x.g END"""
FROM_SCHEDE = """FROM ballot b JOIN v ON v.uri = b.vote
  LEFT JOIN grp g0 ON g0.uri = b.grp LEFT JOIN grp_alias ga ON ga.alias = b.grp
  CROSS JOIN LATERAL (SELECT coalesce(g0.uri, ga.grp, group_at(b.person, v.date)) AS g) x"""
# appartenenze per il gruppo alla data in un join (più svelto di group_at riga per riga): la componente vince sul Misto
CTE_APPARTENENZE = """gm AS (SELECT m.person, m.grp, m.start_date AS da, coalesce(m.end_date, DATE '9999-12-31') AS a,
                                  (g.kind = 'misto_component') AS comp FROM membership m JOIN grp g ON g.uri = m.grp)"""


class ConteggioTroppoLungo(RuntimeError):
    pass


@contextmanager
def tempo_massimo(c: psycopg.Connection, secondi: int = TEMPO):
    """Le query del blocco in una transazione con il loro tempo massimo; oltre, un errore che dice come restringere."""
    try:
        with c.transaction():
            c.execute(f"SET LOCAL statement_timeout = '{int(secondi)}s'")
            c.execute(f"SET LOCAL work_mem = '{MEMORIA}'")      # aggregati in memoria, non ordinati su disco
            yield
    except psycopg.errors.QueryCanceled:
        raise ConteggioTroppoLungo(f"il conteggio ha superato {secondi} secondi: restringi il periodo, il ramo o i filtri") from None


# ---------- gruppi ----------

def catalogo_gruppi(c: psycopg.Connection) -> dict[str, dict]:
    return {r["uri"]: r for r in c.execute("SELECT uri, chamber, kind, name, short_name, part_of FROM grp")}


def etichetta(cat: dict[str, dict], uri: str | None) -> str | None:
    """«Fratelli d'Italia (FDI)»; una componente come «Misto - +Europa (MISTO-+EU-SUEU)»; il Misto senza componente
    come «Misto (MISTO)»."""
    if uri is None or uri.startswith("("):
        return uri
    g = cat.get(uri)
    if g is None:
        return uri
    nome = f"Misto - {g['name']}" if g["kind"] == "misto_component" else g["name"]
    return f"{nome} ({g['short_name']})" if g["short_name"] else nome


def gruppi_chiesti(cat: dict[str, dict], testo: str, chamber: str | None = None) -> list[str]:
    """Gli uri di un gruppo dato per uri, sigla o nome (anche parte del nome); con il Misto vengono le componenti."""
    t = testo.strip().lower()
    nel_ramo = {u: g for u, g in cat.items() if chamber is None or g["chamber"] == chamber}
    trovati = [u for u, g in nel_ramo.items() if t in (u.lower(), (g["short_name"] or "").lower(), g["name"].lower())]
    if not trovati:
        trovati = [u for u, g in nel_ramo.items() if t in g["name"].lower() or t in (g["short_name"] or "").lower()]
    if not trovati:
        raise ValueError(f"gruppo non trovato: {testo}")
    return sorted(set(trovati) | {u for u, g in nel_ramo.items() if g["part_of"] in trovati})


# ---------- pezzi comuni ----------

def _periodo(start: dt.date | None, end: dt.date | None) -> str:
    if start and end:
        return f"dal {start:%d/%m/%Y} al {end:%d/%m/%Y}"
    if start:
        return f"dal {start:%d/%m/%Y}"
    if end:
        return f"fino al {end:%d/%m/%Y}"
    return "tutta la XIX legislatura"


def _ramo(chamber: str | None) -> str:
    return {"camera": "Camera", "senato": "Senato"}.get(chamber or "", "Camera e Senato")


def _estremi(r: dict) -> str:
    return f" dal {r['dal']:%d/%m/%Y} al {r['al']:%d/%m/%Y}" if r.get("dal") else ""


def _filtri(**f) -> str:
    parti = [f"{k} {v}" for k, v in f.items() if v not in (None, [], "")]
    return ("; filtri: " + ", ".join(parti)) if parti else ""


def _dimensioni(group_by: list[str], ammesse: dict[str, str], chamber: str | None, sum_chambers: bool) -> list[str]:
    """Le dimensioni chieste, nell'ordine; senza ramo e senza sum_chambers si aggiunge il ramo."""
    fuori = [d for d in group_by if d not in ammesse]
    if fuori:
        raise ValueError(f"group_by non ammesso: {', '.join(fuori)} (ammessi: {', '.join(ammesse)})")
    dims = list(dict.fromkeys(group_by))
    if chamber is None and not sum_chambers and "ramo" in ammesse and "ramo" not in dims:
        dims.insert(0, "ramo")
    return dims


def _pagina(righe: list[dict], limit: int, offset: int) -> dict:
    limit = min(limit, RIGHE_MAX)
    out = {"rows_total": len(righe), "offset": offset, "rows": righe[offset:offset + limit]}
    if offset + limit < len(righe):
        out["more"] = f"altre {len(righe) - offset - limit} righe: richiama con offset={offset + limit}"
    return out


def _sostituisci_gruppi(righe: list[dict], cat: dict[str, dict], chiavi: tuple[str, ...]) -> None:
    for r in righe:
        for k in chiavi:
            if k in r:
                r[k] = etichetta(cat, r[k]) if r[k] else "(senza gruppo)"


def _sostituisci_persone(c: psycopg.Connection, righe: list[dict], chiave: str = "persona") -> None:
    persone = brevi(c, [r[chiave] for r in righe if r.get(chiave)])
    for r in righe:
        p = persone.get(r.get(chiave))
        if p:
            r[chiave] = p.name
            r["persona_uri"] = p.uri
            r["gruppo_oggi"] = p.group.short_name or p.group.name if p.group else None


def _regex_parole(frase: str) -> str:
    """La frase come espressione regolare di Postgres: parole intere, spazi qualsiasi, apostrofi dritti o curvi."""
    parole = [re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", w) for w in frase.split()]
    return r"\m" + r"\s+".join(parole).replace("'", "['’]") + r"\M"


# ---------- votazioni ----------

FILTRO_VOTI = """v.legislature = %(leg)s AND (%(ramo)s::text IS NULL OR v.chamber = %(ramo)s)
  AND (%(tipo)s::text IS NULL OR v.kind = %(tipo)s) AND (%(finale)s::boolean IS NULL OR v.final = %(finale)s)
  AND (%(segreta)s::boolean IS NULL OR coalesce(v.secret, false) = %(segreta)s)
  AND (%(approvata)s::boolean IS NULL OR v.approved = %(approvata)s)
  AND (%(fiducia)s::boolean IS NULL OR coalesce(v.confidence, false) = %(fiducia)s)
  AND (%(dal)s::date IS NULL OR v.date >= %(dal)s) AND (%(al)s::date IS NULL OR v.date <= %(al)s)
  AND (%(atto)s::text IS NULL OR EXISTS (SELECT 1 FROM vote_act y WHERE y.vote = v.uri AND y.act = %(atto)s))
  AND (%(q)s::text IS NULL OR to_tsvector('italian', coalesce(v.title, '') || ' ' || coalesce(v.description, ''))
       @@ websearch_to_tsquery('italian', %(q)s))"""

DIM_VOTI = {"ramo": "v.chamber", "tipo": "v.kind",
            "esito": "CASE WHEN v.approved THEN 'approvata' WHEN NOT v.approved THEN 'respinta' ELSE 'non indicato' END",
            "anno": "extract(year FROM v.date)::int", "mese": "to_char(v.date, 'YYYY-MM')",
            "finale": "coalesce(v.final, false)", "segreta": "coalesce(v.secret, false)", "fiducia": "coalesce(v.confidence, false)"}


def _parametri_voti(chamber, kind, final, secret, approved, confidence, act, q, start, end) -> dict:
    return {"leg": LEGISLATURA, "ramo": chamber, "tipo": kind, "finale": final, "segreta": secret, "approvata": approved,
            "fiducia": confidence, "atto": act, "q": q, "dal": start, "al": end}


def _descrivi_voti(p: dict) -> str:
    return _filtri(tipo=p["tipo"], finali={True: "sì", False: "no"}.get(p["finale"]),
                   segrete={True: "sì", False: "no"}.get(p["segreta"]), esito={True: "approvate", False: "respinte"}.get(p["approvata"]),
                   fiducia={True: "sì", False: "no"}.get(p["fiducia"]), atto=p["atto"], parole=p["q"])


def conta_votazioni(c: psycopg.Connection, chamber: str | None = None, kind: str | None = None, final: bool | None = None,
                    secret: bool | None = None, approved: bool | None = None, confidence: bool | None = None,
                    act: str | None = None, q: str | None = None, start: dt.date | None = None, end: dt.date | None = None,
                    group_by: list[str] | None = None, sum_chambers: bool = False, limit: int = 100, offset: int = 0) -> dict:
    """Votazioni elettroniche contate per ramo, tipo, esito, anno, mese, finale, segreta, fiducia."""
    dims = _dimensioni(group_by or [], DIM_VOTI, chamber, sum_chambers)
    p = _parametri_voti(chamber, kind, final, secret, approved, confidence, act, q, start, end)
    sel = ", ".join(f"{DIM_VOTI[d]} AS {d}" for d in dims)
    with tempo_massimo(c):
        righe = c.execute(f"""SELECT {sel + ', ' if sel else ''}count(*) AS votazioni, min(v.date) AS dal, max(v.date) AS al
                              FROM vote v WHERE {FILTRO_VOTI} {'GROUP BY ' + ', '.join(map(str, range(1, len(dims) + 1))) if dims else ''}
                              ORDER BY {', '.join(map(str, range(1, len(dims) + 1))) if dims else 1}""", p).fetchall()
    righe = [r for r in righe if r["votazioni"]]
    out = {"counted": f"Votazioni elettroniche, {_ramo(chamber)}, {_periodo(start, end)}{_descrivi_voti(p)}. "
                      f"Fonte: le votazioni pubblicate dai due rami (tabella vote); i rami non sono sommati"
                      f"{'' if not sum_chambers else ' (somma dei due rami chiesta)'}.",
           "total": sum(r["votazioni"] for r in righe)}
    return out | _pagina(righe, limit, offset)


def voto_gruppi(c: psycopg.Connection, chamber: str, kind: str | None = None, final: bool | None = None,
                approved: bool | None = None, confidence: bool | None = None, act: str | None = None, q: str | None = None,
                start: dt.date | None = None, end: dt.date | None = None, groups: list[str] | None = None,
                person: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    """Come ha votato ogni gruppo (il Misto per componente) su un insieme di votazioni palesi: posizioni, coesione,
    accordo fra gruppi; con due gruppi, le votazioni in cui hanno preso posizioni diverse; con una persona, quanto ha
    votato come ciascun gruppo, diviso per il gruppo che aveva al momento del voto."""
    cat = catalogo_gruppi(c)
    scelti: list[str] | None = None
    if groups:
        scelti = []
        for g in groups:
            scelti += [u for u in gruppi_chiesti(cat, g, chamber) if u not in scelti]
    p = _parametri_voti(chamber, kind, final, False, approved, confidence, act, q, start, end)
    alias = {r["alias"]: r["grp"] for r in c.execute("SELECT alias, grp FROM grp_alias")}
    misti = {g["part_of"] for g in cat.values() if g["part_of"]}
    # gruppi della scheda che non chiedono la persona: noti (o versioni note) e non il Misto
    diretti = {u for u in cat if u not in misti} | {a for a, g in alias.items() if g not in misti}

    def gruppo_del_voto(scritto: str | None, alla_data: str | None) -> str | None:
        base = scritto if scritto in cat else alias.get(scritto) or alla_data
        if base in misti and alla_data in cat and cat[alla_data]["part_of"] == base:
            return alla_data
        return base

    with tempo_massimo(c):
        # due passi: le schede con un gruppo noto si contano per gruppo scritto; le altre (il Misto, gruppi sconosciuti)
        # chiedono il gruppo della persona alla data
        conti_sql = """count(*) FILTER (WHERE b.result = 'favor') AS favor, count(*) FILTER (WHERE b.result = 'against') AS against,
                       count(*) FILTER (WHERE b.result = 'abstain') AS abstain"""
        righe = c.execute(f"""
            WITH v AS (SELECT v.uri, v.date FROM vote v WHERE {FILTRO_VOTI})
            SELECT b.vote, b.grp, NULL AS alla_data, {conti_sql} FROM ballot b JOIN v ON v.uri = b.vote
            WHERE b.result IN ('favor', 'against', 'abstain') AND b.grp = ANY(%(diretti)s) GROUP BY 1, 2""",
            p | {"diretti": list(diretti)}).fetchall()
        righe += c.execute(f"""
            WITH v AS (SELECT v.uri, v.date FROM vote v WHERE {FILTRO_VOTI})
            SELECT b.vote, b.grp, group_at(b.person, v.date) AS alla_data, {conti_sql} FROM ballot b JOIN v ON v.uri = b.vote
            WHERE b.result IN ('favor', 'against', 'abstain') AND (b.grp IS NULL OR NOT b.grp = ANY(%(diretti)s)) GROUP BY 1, 2, 3""",
            p | {"diretti": list(diretti)}).fetchall()
        info = c.execute(f"SELECT count(*) AS n, min(v.date) AS dal, max(v.date) AS al FROM vote v WHERE {FILTRO_VOTI}", p).fetchone()
        schede_persona = []
        if person:
            schede_persona = c.execute(f"""
                WITH v AS (SELECT v.uri, v.date FROM vote v WHERE {FILTRO_VOTI})
                SELECT b.vote, b.result, b.grp, group_at(b.person, v.date) AS alla_data FROM ballot b JOIN v ON v.uri = b.vote
                WHERE b.person = ANY(%(ids)s) AND b.result IN ('favor', 'against', 'abstain')""",
                p | {"ids": stessa_persona(c, person)}).fetchall()
            for s in schede_persona:
                s["g"] = gruppo_del_voto(s["grp"], s["alla_data"])
    per_voto: dict[str, dict[str, tuple[int, int, int]]] = defaultdict(dict)
    for r in righe:
        g = gruppo_del_voto(r["grp"], r["alla_data"])
        if g:
            x = per_voto[r["vote"]].get(g, (0, 0, 0))
            per_voto[r["vote"]][g] = (x[0] + r["favor"], x[1] + r["against"], x[2] + r["abstain"])

    def posizione(conti: tuple[int, int, int]) -> str | None:
        m = max(conti)
        if m == 0:
            return None
        return SCELTE[conti.index(m)] if conti.count(m) == 1 else "tie"

    stat: dict[str, dict] = {}
    for gruppi_voto in per_voto.values():
        for g, conti in gruppi_voto.items():
            s = stat.setdefault(g, {"votes": 0, "indice": 0.0, "con_due": 0, "unanimi": 0, "favor": 0, "against": 0, "abstain": 0, "tie": 0})
            n, m = sum(conti), max(conti)
            s["votes"] += 1
            s[posizione(conti)] += 1
            if n >= 2:
                s["con_due"] += 1
                s["indice"] += (m - 0.5 * (n - m)) / n
                s["unanimi"] += m == n
    mostrati = [g for g in stat if scelti is None or g in scelti]
    gruppi = sorted(({"group": etichetta(cat, g), "votes_with_voters": s["votes"],
                      "cohesion": round(s["indice"] / s["con_due"], 3) if s["con_due"] else None,
                      "unanimous_share": round(s["unanimi"] / s["con_due"], 3) if s["con_due"] else None,
                      "positions": {k: s[k] for k in ("favor", "against", "abstain", "tie")}}
                     for g, s in stat.items() if g in mostrati), key=lambda x: (x["votes_with_voters"] < MIN_VOTI_ACCORDO, -(x["cohesion"] or 0)))
    accordo: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for gruppi_voto in per_voto.values():
        pos = {g: posizione(cn) for g, cn in gruppi_voto.items() if g in mostrati}
        for a, b in combinations(sorted(g for g, x in pos.items() if x not in (None, "tie")), 2):
            accordo[(a, b)][0] += 1
            accordo[(a, b)][1] += pos[a] == pos[b]
    breve = {g: (cat.get(g) or {}).get("short_name") or etichetta(cat, g) for g in mostrati}
    matrice: dict[str, dict[str, float]] = defaultdict(dict)
    for (a, b), (n, k) in accordo.items():
        if n >= MIN_VOTI_ACCORDO:
            matrice[breve[a]][breve[b]] = matrice[breve[b]][breve[a]] = round(k / n, 3)
    out = {"counted": f"Votazioni palesi, {_ramo(chamber)}, {_periodo(start, end)}{_descrivi_voti(p)}: {info['n']} votazioni"
                      f"{_estremi(info)}. "
                      "Posizione di un gruppo in un voto = la scelta più frequente fra favorevoli, contrari e astenuti dei suoi membri "
                      "che hanno votato (a pari merito: tie, nessuna posizione). Coesione = indice di accordo di Hix, Noury e Roland, "
                      "(max − ½·(votanti − max)) / votanti, in media sulle votazioni con almeno 2 votanti del gruppo (1 = tutti uguali); "
                      "unanimous_share = quota di quelle votazioni in cui il gruppo ha votato tutto allo stesso modo. Accordo fra due "
                      "gruppi (agreement, per sigla) = quota delle votazioni in cui entrambi hanno una posizione e la posizione è la "
                      f"stessa, solo per le coppie con almeno {MIN_VOTI_ACCORDO} votazioni in comune. Esclusi voti "
                      "segreti, assenti, in missione e presenti non votanti. Gruppo = quello che il ramo scrive nella scheda, alla data "
                      "del voto, il Misto per componente («Misto (…)» = chi è nel Misto senza componente).",
           "votes": info["n"], "groups": gruppi, "agreement": dict(matrice)}
    if scelti is not None and len(groups or []) == 2:
        a_uri = gruppi_chiesti(cat, groups[0], chamber)
        b_uri = gruppi_chiesti(cat, groups[1], chamber)
        if len(a_uri) == 1 and len(b_uri) == 1:
            a, b = a_uri[0], b_uri[0]
            diverse = []
            for voto, gv in per_voto.items():
                pa, pb = posizione(gv.get(a, (0, 0, 0))), posizione(gv.get(b, (0, 0, 0)))
                if pa and pb and pa != pb:
                    diverse.append({"vote": voto, etichetta(cat, a): pa, etichetta(cat, b): pb})
            dettagli = {r["uri"]: r for r in c.execute("SELECT uri, date, number, title, source_url FROM vote WHERE uri = ANY(%s)",
                                                       ([d["vote"] for d in diverse],))}
            for d in diverse:
                x = dettagli.get(d["vote"], {})
                d.update(date=x.get("date"), title=x.get("title"), source_url=x.get("source_url"))
            diverse.sort(key=lambda d: (d["date"] or dt.date.min), reverse=True)
            out["different_positions"] = {"total": len(diverse), "note": "votazioni in cui i due gruppi hanno preso posizioni diverse (tie esclusi)"} \
                | _pagina(diverse, limit, offset)
    if person:
        allineato: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
        for s in schede_persona:
            for g, conti in per_voto.get(s["vote"], {}).items():
                if g == s["g"]:                    # il gruppo della persona senza il suo voto
                    conti = tuple(n - (k == s["result"]) for n, k in zip(conti, SCELTE))
                pos = posizione(conti)
                if pos in (None, "tie"):
                    continue
                allineato[(s["g"], g)][0] += 1
                allineato[(s["g"], g)][1] += pos == s["result"]
        out["person"] = {"uri": person, "votes_cast": len(schede_persona),
                         "note": "quota delle votazioni in cui la persona ha votato come la posizione del gruppo (senza il suo voto), "
                                 "divisa per il gruppo della persona nella scheda di quel voto",
                         "alignment": sorted(({"own_group_at_vote": etichetta(cat, mio), "compared_with": etichetta(cat, g),
                                               "votes": n, "same": k, "share": round(k / n, 3)}
                                              for (mio, g), (n, k) in allineato.items()
                                              if n and (scelti is None or g in scelti or g == mio)),
                                             key=lambda x: (x["own_group_at_vote"] or "", -x["share"]))}
    return out


ORDINI_PRESENZE = {"voted": "voted DESC", "absent": "absent DESC", "mission": "mission DESC", "favor": "favor DESC",
                   "against": "against DESC", "abstain": "abstain DESC"}


def presenze(c: psycopg.Connection, chamber: str, persons: list[str] | None = None, group: str | None = None,
             government: bool = False, kind: str | None = None, final: bool | None = None, start: dt.date | None = None,
             end: dt.date | None = None, order_by: str = "voted", limit: int = 50, offset: int = 0) -> dict:
    """Partecipazione al voto per persona: favorevoli, contrari, astenuti, voti segreti dati, assenze, missioni."""
    if order_by not in ORDINI_PRESENZE:
        raise ValueError(f"order_by ammessi: {', '.join(ORDINI_PRESENZE)}")
    cat = catalogo_gruppi(c)
    p = _parametri_voti(chamber, kind, final, None, None, None, None, None, start, end)
    chi, ids_di = "", {}
    if persons:
        for u in persons:
            for i in stessa_persona(c, u):
                ids_di[i] = u
        chi = "AND b.person = ANY(%(ids)s)"
    elif government:
        # chi ha avuto un incarico in un governo nato nella legislatura mentre aveva il mandato nel ramo
        for r in c.execute("""SELECT DISTINCT o.person, m.person AS id FROM office o
                              JOIN LATERAL (SELECT o.person AS u UNION SELECT same_as FROM person_same_as WHERE person = o.person
                                            UNION SELECT person FROM person_same_as WHERE same_as = o.person) ids ON true
                              JOIN mandate m ON m.person = ids.u AND m.chamber = %(ramo)s AND m.legislature = %(leg)s
                               AND m.start_date <= coalesce(o.end_date, current_date) AND coalesce(m.end_date, current_date) >= o.start_date
                              JOIN government gv ON o.target = gv.uri OR o.target LIKE gv.uri || ':%%'
                              WHERE gv.start_date >= (SELECT min(start_date) FROM mandate WHERE legislature = %(leg)s)""", p).fetchall():
            ids_di[r["id"]] = r["person"]
        chi = "AND b.person = ANY(%(ids)s)"
    gruppi = gruppi_chiesti(cat, group, chamber) if group else None
    if gruppi:
        chi += f" AND ({SQL_GRUPPO_VOTO}) = ANY(%(gruppi)s)"
    with tempo_massimo(c):
        righe = c.execute(f"""
            WITH v AS (SELECT v.uri, v.date FROM vote v WHERE {FILTRO_VOTI})
            SELECT b.person, count(*) AS ballots, count(*) FILTER (WHERE b.result = 'favor') AS favor,
                   count(*) FILTER (WHERE b.result = 'against') AS against, count(*) FILTER (WHERE b.result = 'abstain') AS abstain,
                   count(*) FILTER (WHERE b.result = 'voted') AS secret_voted, count(*) FILTER (WHERE b.result = 'absent') AS absent,
                   count(*) FILTER (WHERE b.result = 'mission') AS mission, count(*) FILTER (WHERE b.result = 'chair') AS chair,
                   count(*) FILTER (WHERE b.result NOT IN ('favor', 'against', 'abstain', 'voted', 'absent', 'mission', 'chair')) AS other
            {FROM_SCHEDE} WHERE true {chi} GROUP BY 1""", p | {"ids": list(ids_di), "gruppi": gruppi}).fetchall()
        n = c.execute(f"SELECT count(*) AS n, min(v.date) AS dal, max(v.date) AS al FROM vote v WHERE {FILTRO_VOTI}", p).fetchone()
    per_persona: dict[str, dict] = {}
    for r in righe:
        u = ids_di.get(r["person"], r["person"])
        x = per_persona.setdefault(u, {"persona": u} | {k: 0 for k in r if k != "person"})
        for k, val in r.items():
            if k != "person":
                x[k] += val
    for x in per_persona.values():
        x["voted"] = x["favor"] + x["against"] + x["abstain"] + x["secret_voted"]
    elenco = sorted(per_persona.values(), key=lambda x: (-x[order_by.split()[0]], x["persona"]))
    pagina = _pagina(elenco, limit, offset)
    _sostituisci_persone(c, pagina["rows"])
    if government:
        incarichi = defaultdict(list)
        for o in c.execute("""SELECT o.person, o.title, o.start_date, o.end_date, coalesce(mi.name, gv.name) AS dove FROM office o
                              LEFT JOIN ministry mi ON mi.uri = o.target LEFT JOIN government gv ON gv.uri = o.target
                              WHERE o.target LIKE 'it:gov:%%' AND o.person = ANY(%s) ORDER BY o.start_date""",
                           ([r["persona_uri"] for r in pagina["rows"] if r.get("persona_uri")],)):
            incarichi[o["person"]].append(f"{o['title']} {o['dove'] or ''} dal {o['start_date']:%d/%m/%Y}"
                                          + (f" al {o['end_date']:%d/%m/%Y}" if o["end_date"] else ""))
        for r in pagina["rows"]:
            r["government_offices"] = incarichi.get(r.get("persona_uri"), [])
    chi_testo = ("le persone indicate" if persons else "chi ha avuto un incarico in un governo nato nella XIX durante il mandato nel ramo" if government
                 else f"i membri del gruppo {group} quando erano nel gruppo" if group else "tutti i membri del ramo")
    return {"counted": f"Schede di voto, {_ramo(chamber)}, {_periodo(start, end)}{_descrivi_voti(p)}: {n['n']} votazioni"
                       f"{_estremi(n)}; persone: {chi_testo}. "
                       "voted = favorevoli + contrari + astenuti + voti segreti dati; mission = in missione (per incarico, non è assenza); "
                       "absent = assente; chair = presiede. Le votazioni contate sono quelle dell'insieme, anche fuori dal periodo "
                       "di un incarico; chi ha avuto il mandato per parte del periodo ha meno schede (ballots).",
            "votes_in_set": n["n"], "persons_total": len(elenco)} | pagina


# ---------- interventi e reazioni ----------

DIM_INTERVENTI = {"ramo": "st.chamber", "sede": "CASE WHEN st.body LIKE '%%:aula' THEN 'aula' ELSE 'commissioni' END",
                  "organo": "coalesce(st.body_name, st.body)", "anno": "extract(year FROM st.date)::int",
                  "mese": "to_char(st.date, 'YYYY-MM')", "persona": "s.person", "gruppo": SQL_GRUPPO_ORATORE, "ruolo": SQL_RUOLO}
RUOLI = ("parlamentare", "governo", "presidenza", "relatore", "altro")


def _filtro_sedute(chamber, body, start, end, person_ids) -> str:
    return """(%(ramo)s::text IS NULL OR st.chamber = %(ramo)s)
      AND (%(org)s::text IS NULL OR (%(org)s = 'aula' AND st.body LIKE '%%:aula') OR (%(org)s = 'commissioni' AND st.body NOT LIKE '%%:aula')
           OR st.body = %(org)s)
      AND (%(dal)s::date IS NULL OR st.date >= %(dal)s) AND (%(al)s::date IS NULL OR st.date <= %(al)s)
      AND (%(pers)s::text[] IS NULL OR s.person = ANY(%(pers)s))"""


def conta_interventi(c: psycopg.Connection, chamber: str | None = None, body: str | None = "aula", phrase: str | None = None,
                     person: str | None = None, group: str | None = None, role: str | None = None,
                     start: dt.date | None = None, end: dt.date | None = None, include_summaries: bool = True,
                     words: bool = False, group_by: list[str] | None = None, order_by: str = "interventi",
                     sum_chambers: bool = False, limit: int = 50, offset: int = 0) -> dict:
    """Interventi contati per ramo, sede, organo, anno, mese, persona, gruppo, ruolo; con `phrase`, solo quelli che la
    contengono e le volte che ricorre; con `words`, anche le parole."""
    if role and role not in RUOLI:
        raise ValueError(f"role ammessi: {', '.join(RUOLI)}")
    if order_by not in ("interventi", "parole", "occorrenze"):
        raise ValueError("order_by ammessi: interventi, parole, occorrenze")
    words = words or order_by == "parole"
    if order_by == "occorrenze" and not phrase:
        raise ValueError("occorrenze vuole phrase")
    dims = _dimensioni(group_by or [], DIM_INTERVENTI, chamber, sum_chambers)
    cat = catalogo_gruppi(c)
    gruppi = gruppi_chiesti(cat, group, chamber) if group else None
    p = {"ramo": chamber, "org": body, "dal": start, "al": end, "pers": stessa_persona(c, person) if person else None,
         "frase": phrase, "re": _regex_parole(phrase) if phrase else None, "ruolo": role, "gruppi": gruppi, "somm": include_summaries}
    misure = ["count(*) AS interventi"]
    if words:
        misure.append("sum(regexp_count(s.text, '\\S+')) AS parole")
    if phrase:
        misure.append("sum(regexp_count(s.text, %(re)s, 1, 'i')) AS occorrenze")
    filtro = _filtro_sedute(chamber, body, start, end, p["pers"]) + " AND (%(somm)s OR s.kind IS DISTINCT FROM 'summary')"
    if phrase:
        filtro += """ AND (numnode(phraseto_tsquery('italian', %(frase)s)) = 0
                           OR to_tsvector('italian', s.text) @@ phraseto_tsquery('italian', %(frase)s)) AND s.text ~* %(re)s"""
    if role:
        filtro += f" AND ({SQL_RUOLO}) = %(ruolo)s"
    if gruppi:
        filtro += f" AND ({SQL_GRUPPO_ORATORE}) = ANY(%(gruppi)s)"
    sel = ", ".join(f"{DIM_INTERVENTI[d]} AS {d}" for d in dims)
    gby = ("GROUP BY " + ", ".join(map(str, range(1, len(dims) + 1)))) if dims else ""
    with tempo_massimo(c):
        righe = c.execute(f"""SELECT {sel + ', ' if sel else ''}{', '.join(misure)}, min(st.date) AS dal, max(st.date) AS al
                              FROM speech s JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
                              WHERE {filtro} {gby}""", p).fetchall()
    righe = [r for r in righe if r["interventi"]]
    totali = {m: sum(r.get(m) or 0 for r in righe) for m in ("interventi", "parole", "occorrenze") if m in (righe[0] if righe else {})}
    righe.sort(key=lambda r: -(r.get(order_by) or 0))
    pagina = _pagina(righe, limit, offset)
    _sostituisci_gruppi(pagina["rows"], cat, ("gruppo",))
    if "persona" in dims:
        _sostituisci_persone(c, pagina["rows"])
    sede = {"aula": "sedute d'Aula", "commissioni": "sedute di commissione", None: "Aula e commissioni"}.get(body, f"organo {body}")
    return {"counted": f"Interventi, {_ramo(chamber)}, {sede}, {_periodo(start, end)}"
                       f"{_filtri(frase=repr(phrase) if phrase else None, persona=person, gruppo=group, ruolo=role)}. "
                       + (f"Con la frase: interventi che contengono «{phrase}» a parole intere, maiuscole indifferenti; occorrenze = "
                          "le volte che ricorre (un intervento conta una volta in «interventi»). " if phrase else "")
                       + ("Parole = parti del testo separate da spazi. " if words else "")
                       + "Un intervento è un turno di parola nel resoconto"
                       + ("; i riassunti delle commissioni (resoconto sommario) contano come interventi" if include_summaries and body != "aula" else "")
                       + ". Ruolo: presidenza (chi presiede), governo (incarico di governo alla data), relatore, parlamentare, altro "
                         "(auditi ed esterni). Gruppo = gruppo di chi parla alla data (group_at), il Misto per componente, solo per i "
                         "parlamentari: gli altri ruoli sono «(senza gruppo)». Fonte: resoconti stenografici d'Aula e di commissione, "
                         "resoconti sommari delle commissioni.",
            "totals": totali} | pagina


DIM_REAZIONI = {"ramo": "st.chamber", "tipo": "r.kind", "anno": "extract(year FROM st.date)::int", "mese": "to_char(st.date, 'YYYY-MM')",
                "gruppo_che_reagisce": "f.grp", "gruppo_oratore": SQL_GRUPPO_ORATORE, "ruolo_oratore": SQL_RUOLO,
                "persona_oratore": "s.person"}


def conta_reazioni(c: psycopg.Connection, chamber: str | None = None, kinds: list[str] | None = None, body: str | None = "aula",
                   start: dt.date | None = None, end: dt.date | None = None, speaker: str | None = None,
                   speaker_group: str | None = None, from_group: str | None = None, speaker_role: str | None = None,
                   contains: str | None = None, group_by: list[str] | None = None, sum_chambers: bool = False,
                   limit: int = 100, offset: int = 0) -> dict:
    """Reazioni registrate nel resoconto (applausi, proteste, commenti…) contate per tipo, ramo, periodo, gruppo che
    reagisce, gruppo, ruolo o persona di chi parla."""
    if speaker_role and speaker_role not in RUOLI:
        raise ValueError(f"speaker_role ammessi: {', '.join(RUOLI)}")
    dims = _dimensioni(group_by or [], DIM_REAZIONI, chamber, sum_chambers)
    cat = catalogo_gruppi(c)
    da_gruppi = gruppi_chiesti(cat, from_group, chamber) if from_group else None
    di_gruppi = gruppi_chiesti(cat, speaker_group, chamber) if speaker_group else None
    per_gruppo = "gruppo_che_reagisce" in dims or da_gruppi
    p = {"ramo": chamber, "org": body, "dal": start, "al": end, "pers": stessa_persona(c, speaker) if speaker else None,
         "tipi": kinds, "da": da_gruppi, "di": di_gruppi, "ruolo": speaker_role, "testo": contains}
    filtro = _filtro_sedute(chamber, body, start, end, p["pers"]) + """ AND (%(tipi)s::text[] IS NULL OR r.kind = ANY(%(tipi)s))
        AND (%(testo)s::text IS NULL OR r.raw ILIKE '%%' || %(testo)s || '%%')"""
    if da_gruppi:
        filtro += " AND f.grp = ANY(%(da)s)"
    if di_gruppi:
        filtro += f" AND ({SQL_GRUPPO_ORATORE}) = ANY(%(di)s)"
    if speaker_role:
        filtro += f" AND ({SQL_RUOLO}) = %(ruolo)s"
    sel = ", ".join(f"{DIM_REAZIONI[d]} AS {d}" for d in dims)
    gby = ("GROUP BY " + ", ".join(map(str, range(1, len(dims) + 1)))) if dims else ""
    unione = "LEFT JOIN reaction_from f ON f.reaction = r.uri AND f.grp IS NOT NULL" if per_gruppo else ""
    with tempo_massimo(c):
        righe = c.execute(f"""SELECT {sel + ', ' if sel else ''}count(*) AS reazioni
                              FROM reaction r JOIN speech s ON s.uri = r.speech JOIN agenda_item i ON i.uri = s.item
                              JOIN sitting st ON st.uri = i.sitting {unione}
                              WHERE {filtro} {gby}""", p).fetchall()
    righe = [r for r in righe if r["reazioni"]]
    righe.sort(key=lambda r: -r["reazioni"])
    pagina = _pagina(righe, limit, offset)
    _sostituisci_gruppi(pagina["rows"], cat, ("gruppo_oratore",))
    for r in pagina["rows"]:
        if "gruppo_che_reagisce" in r:
            r["gruppo_che_reagisce"] = etichetta(cat, r["gruppo_che_reagisce"]) if r["gruppo_che_reagisce"] else "(nessun gruppo nominato)"
    if "persona_oratore" in dims:
        _sostituisci_persone(c, pagina["rows"], "persona_oratore")
    sede = {"aula": "sedute d'Aula", "commissioni": "sedute di commissione", None: "Aula e commissioni"}.get(body, f"organo {body}")
    return {"counted": f"Reazioni scritte nel resoconto dentro gli interventi (didascalie tra parentesi), {_ramo(chamber)}, {sede}, "
                       f"{_periodo(start, end)}{_filtri(tipi=', '.join(kinds) if kinds else None, oratore=speaker, gruppo_oratore=speaker_group, gruppo_che_reagisce=from_group, ruolo_oratore=speaker_role, testo=contains)}. "
                       "Tipi: applause, protests, comments, noise, laughter, ironic_applause, altercation, interruption, action, "
                       "procedure, other. "
                       + ("Per gruppo che reagisce una reazione conta una volta per ogni gruppo nominato («Applausi dei gruppi PD-IDP e AVS» "
                          "conta per entrambi); «(nessun gruppo nominato)» = reazioni senza gruppo riconosciuto («Applausi», «dai banchi "
                          "della maggioranza», singoli deputati). Gruppo che reagisce alla data della seduta, il Misto per componente. "
                          if per_gruppo else "")
                       + "Gruppo dell'oratore alla data (group_at), solo per i parlamentari; ruolo dell'oratore come in conta_interventi. "
                         "Una reazione non dice sempre a chi è rivolta: il resoconto la registra dentro l'intervento.",
            "total": sum(r["reazioni"] for r in righe)} | pagina


# ---------- atti ----------

SQL_GRUPPO_PRIMO = """(SELECT coalesce(
    (SELECT x.g FROM act_sponsor sp
       CROSS JOIN LATERAL (SELECT sp.person AS id UNION SELECT same_as FROM person_same_as WHERE person = sp.person
                           UNION SELECT person FROM person_same_as WHERE same_as = sp.person) ids
       CROSS JOIN LATERAL (SELECT group_at(ids.id, coalesce(a.date, current_date)) AS g) x
       WHERE sp.act = a.uri AND sp.first AND x.g LIKE 'it:' || a.chamber || ':%%' LIMIT 1),
    (SELECT '(governo)' FROM act_sponsor sp WHERE sp.act = a.uri AND sp.first AND sp.as_office IS NOT NULL LIMIT 1),
    (SELECT '(primo firmatario senza gruppo)' FROM act_sponsor sp WHERE sp.act = a.uri AND sp.first LIMIT 1)))"""
DIM_ATTI = {"ramo": "a.chamber", "tipo": "a.kind", "iniziativa": SQL_INIZIATIVA, "gruppo_primo_firmatario": SQL_GRUPPO_PRIMO,
            "primo_firmatario": "(SELECT min(sp.person) FROM act_sponsor sp WHERE sp.act = a.uri AND sp.first)",
            "anno": "extract(year FROM a.date)::int", "mese": "to_char(a.date, 'YYYY-MM')",
            "legge": "CASE WHEN a.law_number IS NOT NULL THEN 'diventato legge' ELSE 'no' END"}
DIM_LEGGI = {"iniziativa": "l.iniziativa", "anno": "l.anno", "mese": "to_char(l.data, 'YYYY-MM')",
             "costituzionale": "l.costituzionale", "conversione_decreto": "l.decreto"}


def _temi(c: psycopg.Connection, tema: str) -> list[dict]:
    """I concetti dei thesauri con il tema nel nome e quelli più specifici sotto di loro (fino a quattro livelli)."""
    return c.execute("""
        WITH RECURSIVE t(uri, label, livello) AS (
          SELECT uri, label_it, 0 FROM concept WHERE norm_nome(label_it) LIKE '%%' || norm_nome(%(t)s) || '%%'
          UNION SELECT k.uri, k.label_it, t.livello + 1 FROM concept k JOIN t ON t.uri = ANY(k.broader) WHERE t.livello < 4)
        SELECT DISTINCT ON (uri) uri, label FROM t ORDER BY uri, livello""", {"t": tema}).fetchall()


def conta_atti(c: psycopg.Connection, chamber: str | None = None, kind: str | None = None, initiative: str | None = None,
               q: str | None = None, subject: str | None = None, signer: str | None = None, first_signer: bool = False,
               group: str | None = None, became_law: bool | None = None, start: dt.date | None = None, end: dt.date | None = None,
               laws: bool = False, group_by: list[str] | None = None, sum_chambers: bool = False,
               limit: int = 100, offset: int = 0, addressee: str | None = None) -> dict:
    """Atti contati per ramo, tipo, iniziativa, gruppo del primo firmatario, primo firmatario, anno, mese, legge; con
    `addressee` solo quelli rivolti a un ministero (parte del nome: «interno», «salute»); con
    `laws`, le leggi approvate contate una volta sola anche se l'atto è in tutti e due i rami."""
    cat = catalogo_gruppi(c)
    gruppi = gruppi_chiesti(cat, group, chamber) if group else None
    temi = _temi(c, subject) if subject else None
    if subject and not temi:
        raise ValueError(f"nessun tema dei thesauri contiene «{subject}»: prova un'altra parola")
    ini = initiative.strip().lower() if initiative else None
    p = {"leg": LEGISLATURA, "ramo": chamber, "tipo": kind, "q": q, "dal": start, "al": end, "legge": became_law,
         "ini": ini if ini in INIZIATIVE else None, "ini_testo": None if ini in INIZIATIVE else initiative,
         "firm": stessa_persona(c, signer) if signer else None, "primo": first_signer, "gruppi": gruppi,
         "temi": [t["uri"] for t in temi] if temi else None, "min": addressee}
    filtro = f"""a.legislature = %(leg)s AND (%(ramo)s::text IS NULL OR a.chamber = %(ramo)s) AND (%(tipo)s::text IS NULL OR a.kind = %(tipo)s)
        AND (%(dal)s::date IS NULL OR a.date >= %(dal)s) AND (%(al)s::date IS NULL OR a.date <= %(al)s)
        AND (%(legge)s::boolean IS NULL OR (a.law_number IS NOT NULL) = %(legge)s)
        AND (%(ini)s::text IS NULL OR ({SQL_INIZIATIVA}) = %(ini)s)
        AND (%(ini_testo)s::text IS NULL OR a.initiative ILIKE '%%' || %(ini_testo)s || '%%')
        AND (%(q)s::text IS NULL OR to_tsvector('italian', coalesce(a.title, '')) @@ websearch_to_tsquery('italian', %(q)s))
        AND (%(firm)s::text[] IS NULL OR EXISTS (SELECT 1 FROM act_sponsor s WHERE s.act = a.uri AND s.person = ANY(%(firm)s)
                                                  AND (s.first OR NOT %(primo)s)))
        AND (%(temi)s::text[] IS NULL OR EXISTS (SELECT 1 FROM act_subject x WHERE x.act = a.uri AND x.concept = ANY(%(temi)s)))
        AND (%(min)s::text IS NULL OR EXISTS (SELECT 1 FROM act_addressee d JOIN ministry m ON m.uri = d.ministry
                                               WHERE d.act = a.uri AND m.name ILIKE '%%' || %(min)s || '%%'))"""
    if gruppi:
        filtro += f" AND {SQL_GRUPPO_PRIMO} = ANY(%(gruppi)s)"
    descr = _filtri(tipo=kind, iniziativa=initiative, parole_del_titolo=q, firmatario=signer, rivolti_al_ministero=addressee,
                    gruppo_del_primo_firmatario=group, diventati_legge={True: "sì", False: "no"}.get(became_law))
    if temi:
        nomi = sorted({t["label"] for t in temi})
        descr += f"; tema «{subject}»: atti con almeno uno di {len(temi)} concetti dei thesauri ({', '.join(nomi[:12])}{'…' if len(nomi) > 12 else ''})"
    with tempo_massimo(c):
        if laws:
            dims = _dimensioni(group_by or [], DIM_LEGGI, None, True)
            sel = ", ".join(f"{DIM_LEGGI[d]} AS {d}" for d in dims)
            gby = ("GROUP BY " + ", ".join(map(str, range(1, len(dims) + 1)))) if dims else ""
            righe = c.execute(f"""
                WITH x AS (SELECT a.law_number, a.law_date, coalesce(a.constitutional, false) AS cost, a.title, {SQL_INIZIATIVA} AS ini
                           FROM act a WHERE {filtro} AND a.law_number IS NOT NULL AND a.law_date < DATE '2100-01-01'),
                l AS (SELECT law_number, extract(year FROM law_date)::int AS anno, cost AS costituzionale, min(law_date) AS data,
                             CASE WHEN count(DISTINCT ini) > 1 THEN 'mista' ELSE coalesce(max(ini), 'non indicata') END AS iniziativa,
                             bool_or(title ILIKE '%%conversione in legge%%') AS decreto
                      FROM x GROUP BY 1, 2, 3)
                SELECT {sel + ', ' if sel else ''}count(*) AS leggi, min(l.data) AS dal, max(l.data) AS al FROM l {gby}""", p).fetchall()
            righe = [r for r in righe if r["leggi"]]
            righe.sort(key=lambda r: -r["leggi"])
            return {"counted": f"Leggi nate da atti della XIX, {_ramo(chamber)}, atti presentati {_periodo(start, end)}{descr}. "
                               "Una legge = numero e anno della legge (law_number, law_date), ordinarie e costituzionali a parte: conta "
                               "una volta anche se l'atto compare in tutti e due i rami o in più atti. Iniziativa per categoria (governo, "
                               "parlamentare, regione, cnel, popolare), «mista» se gli atti di una legge ne hanno più d'una; "
                               "conversione_decreto = titolo con «conversione in legge». Esclusi i testi approvati non ancora pubblicati "
                               "(senza numero di legge).",
                    "total": sum(r["leggi"] for r in righe)} | _pagina(righe, limit, offset)
        dims = _dimensioni(group_by or [], DIM_ATTI, chamber, sum_chambers)
        sel = ", ".join(f"{DIM_ATTI[d]} AS {d}" for d in dims)
        gby = ("GROUP BY " + ", ".join(map(str, range(1, len(dims) + 1)))) if dims else ""
        righe = c.execute(f"SELECT {sel + ', ' if sel else ''}count(*) AS atti, min(a.date) AS dal, max(a.date) AS al FROM act a WHERE {filtro} {gby}",
                          p).fetchall()
    righe = [r for r in righe if r["atti"]]
    righe.sort(key=lambda r: -r["atti"])
    pagina = _pagina(righe, limit, offset)
    _sostituisci_gruppi(pagina["rows"], cat, ("gruppo_primo_firmatario",))
    if "primo_firmatario" in dims:
        _sostituisci_persone(c, pagina["rows"], "primo_firmatario")
    return {"counted": f"Atti della XIX, {_ramo(chamber)}, presentati {_periodo(start, end)}{descr}. Tipi: bill (progetti di legge), "
                       "written_question, oral_question, committee_question, interpellation, motion, resolution, agenda_order… "
                       "Iniziativa per categoria: alla Camera dalla fonte (solo i progetti di legge), al Senato dal testo del "
                       "presentatore; senza categoria = non indicata dalla fonte. Gruppo del primo firmatario alla data dell'atto, il "
                       "Misto per componente; «(governo)» = primo firmatario un membro del governo come tale.",
            "total": sum(r["atti"] for r in righe)} | pagina


# ---------- emendamenti ----------

DIM_EMENDAMENTI = {"ramo": "p.ramo", "atto": "p.act", "sede": "p.venue", "esito": "p.esito", "anno": "p.anno",
                   "gruppo_firmatario": "g1", "coppia_gruppi": "g1, g2"}


def conta_emendamenti(c: psycopg.Connection, chamber: str | None = None, act: str | None = None, outcome: str | None = None,
                      venue: str | None = None, group: str | None = None, start: dt.date | None = None, end: dt.date | None = None,
                      cross_group: bool = False, group_by: list[str] | None = None, sum_chambers: bool = False,
                      limit: int = 100, offset: int = 0) -> dict:
    """Proposte emendative contate per ramo, atto, sede, esito, anno, gruppo dei firmatari o coppia di gruppi che
    cofirmano."""
    dims = _dimensioni(group_by or [], DIM_EMENDAMENTI, chamber, sum_chambers)
    if "gruppo_firmatario" in dims and "coppia_gruppi" in dims:
        raise ValueError("gruppo_firmatario e coppia_gruppi non vanno insieme")
    cat = catalogo_gruppi(c)
    gruppi = gruppi_chiesti(cat, group, chamber) if group else None
    p = {"ramo": chamber, "atto": act, "esito": outcome, "sede": venue, "dal": start, "al": end, "gruppi": gruppi}
    espansione = ""
    if "coppia_gruppi" in dims:
        espansione = "CROSS JOIN LATERAL unnest(p.gs) AS g1 CROSS JOIN LATERAL unnest(p.gs) AS g2"
        dove = "g1 < g2"
    elif "gruppo_firmatario" in dims:
        espansione, dove = "CROSS JOIN LATERAL unnest(p.gs) AS g1", "true"
    else:
        dove = "true"
    sel = ", ".join(f"{DIM_EMENDAMENTI[d]}" if d == "coppia_gruppi" else f"{DIM_EMENDAMENTI[d]} AS {d}" for d in dims)
    n_col = sum(2 if d == "coppia_gruppi" else 1 for d in dims)
    gby = ("GROUP BY " + ", ".join(map(str, range(1, n_col + 1)))) if dims else ""
    with tempo_massimo(c):
        righe = c.execute(f"""
            WITH {CTE_APPARTENENZE},
            e AS (SELECT e.uri, e.act, e.venue, e.number, e.outcome, split_part(e.uri, ':', 2) AS ramo,
                         coalesce(e.sitting_date, e.presented) AS d FROM amendment e
                  WHERE (%(ramo)s::text IS NULL OR e.uri LIKE 'it:' || %(ramo)s || ':%%') AND (%(atto)s::text IS NULL OR e.act = %(atto)s)
                    AND (%(esito)s::text IS NULL OR e.outcome = %(esito)s) AND (%(sede)s::text IS NULL OR e.venue = %(sede)s)
                    AND (%(dal)s::date IS NULL OR coalesce(e.sitting_date, e.presented) >= %(dal)s)
                    AND (%(al)s::date IS NULL OR coalesce(e.sitting_date, e.presented) <= %(al)s)),
            f AS (SELECT DISTINCT ON (s.amendment, s.ord) e.ramo, e.act, e.venue, e.number, gm.grp AS g
                  FROM e JOIN amendment_signer s ON s.amendment = e.uri JOIN gm ON gm.person = s.person AND e.d BETWEEN gm.da AND gm.a
                  ORDER BY s.amendment, s.ord, gm.comp DESC),
            pg AS (SELECT ramo, act, venue, number, array_agg(DISTINCT g) AS gs FROM f GROUP BY 1, 2, 3, 4),
            p AS (SELECT e.ramo, e.act, e.venue, e.number, min(e.outcome) AS esito, extract(year FROM min(e.d))::int AS anno, pg.gs
                  FROM e LEFT JOIN pg USING (ramo, act, venue, number) GROUP BY 1, 2, 3, 4, pg.gs)
            SELECT {sel + ', ' if sel else ''}count(*) AS proposte FROM p {espansione}
            WHERE {dove} AND (NOT %(cross)s OR coalesce(cardinality(p.gs), 0) > 1) AND (%(gruppi)s::text[] IS NULL OR p.gs && %(gruppi)s) {gby}""",
            p | {"cross": cross_group}).fetchall()
    righe = [r for r in righe if r["proposte"]]
    righe.sort(key=lambda r: -r["proposte"])
    pagina = _pagina(righe, limit, offset)
    _sostituisci_gruppi(pagina["rows"], cat, ("gruppo_firmatario", "g1", "g2"))
    for r in pagina["rows"]:
        if "g1" in r and "g2" in r:
            r["coppia_gruppi"] = [r.pop("g1"), r.pop("g2")]
        elif "g1" in r:
            r["gruppo_firmatario"] = r.pop("g1")
    return {"counted": f"Proposte emendative, {_ramo(chamber)}, {_periodo(start, end)}"
                       f"{_filtri(atto=act, esito=outcome, sede=venue, gruppo=group, solo_cofirmate_da_più_gruppi='sì' if cross_group else None)}. "
                       "Una proposta = atto, sede e numero (le riformulazioni con lo stesso numero contano una volta); data = seduta "
                       "o presentazione. Gruppo di ogni firmatario alla data, il Misto per componente; firme senza persona (governo, "
                       "relatori) escluse. Per gruppo: proposte con almeno un firmatario del gruppo; per coppia: proposte con almeno un "
                       "firmatario di ciascuno dei due gruppi. Esito: quello registrato (se le righe ne hanno più d'uno, il primo in "
                       "ordine alfabetico). Fonte: i fascicoli degli emendamenti caricati, la cui completezza non è verificata.",
            "total": sum(r["proposte"] for r in righe) if "coppia_gruppi" not in dims and "gruppo_firmatario" not in dims else None} | pagina


# ---------- cambi di gruppo ----------

def cambi_gruppo(c: psycopg.Connection, chamber: str | None = None, start: dt.date | None = None, end: dt.date | None = None,
                 person: str | None = None, group: str | None = None, components: bool = False,
                 limit: int = 100, offset: int = 0) -> dict:
    """I passaggi da un gruppo a un altro nella legislatura, con il totale delle persone e dei passaggi per ramo."""
    cat = catalogo_gruppi(c)
    gruppi = gruppi_chiesti(cat, group, chamber) if group else None
    with tempo_massimo(c):
        righe = c.execute(f"""
            WITH m AS (SELECT m.person, g.chamber, m.start_date, m.end_date,
                              {'m.grp' if components else "coalesce(CASE WHEN g.kind = 'misto_component' THEN g.part_of END, g.uri)"} AS gg
                       FROM membership m JOIN grp g ON g.uri = m.grp
                       WHERE g.legislature = %(leg)s AND (%(ramo)s::text IS NULL OR g.chamber = %(ramo)s)
                         AND (m.end_date IS NULL OR m.end_date >= DATE '2022-11-01')
                         {'' if not components else '''AND NOT EXISTS (SELECT 1 FROM membership m2 JOIN grp k ON k.uri = m2.grp
                              WHERE k.part_of = g.uri AND m2.person = m.person AND m2.start_date <= coalesce(m.end_date, current_date)
                                AND coalesce(m2.end_date, current_date) >= m.start_date)'''}),
            o AS (SELECT *, lag(gg) OVER (PARTITION BY person, chamber ORDER BY start_date, end_date NULLS LAST) AS prima FROM m)
            SELECT person, chamber, start_date AS date, prima AS da, gg AS a FROM o
            WHERE prima IS NOT NULL AND prima <> gg
              AND (%(dal)s::date IS NULL OR start_date >= %(dal)s) AND (%(al)s::date IS NULL OR start_date <= %(al)s)
              AND (%(pers)s::text[] IS NULL OR person = ANY(%(pers)s))
              AND (%(gruppi)s::text[] IS NULL OR prima = ANY(%(gruppi)s) OR gg = ANY(%(gruppi)s))
            ORDER BY start_date DESC, person""",
            {"leg": LEGISLATURA, "ramo": chamber, "dal": start, "al": end, "pers": stessa_persona(c, person) if person else None,
             "gruppi": gruppi}).fetchall()
    per_ramo = {}
    for r in righe:
        x = per_ramo.setdefault(r["chamber"], {"persons": set(), "changes": 0})
        x["persons"].add(r["person"])
        x["changes"] += 1
    elenco = [{"persona": r["person"], "ramo": r["chamber"], "date": r["date"], "from": etichetta(cat, r["da"]),
               "to": etichetta(cat, r["a"])} for r in righe]
    pagina = _pagina(elenco, limit, offset)
    _sostituisci_persone(c, pagina["rows"])
    return {"counted": f"Passaggi di gruppo, {_ramo(chamber)}, {_periodo(start, end)}{_filtri(persona=person, gruppo=group)}. "
                       + ("Conta anche l'ingresso o l'uscita da una componente del Misto. " if components else
                          "Gruppo = gruppo parlamentare, con le componenti del Misto ricondotte al Misto: entrare in una componente "
                          "restando nel Misto non conta. ")
                       + "Esclusi i passaggi tecnici dell'ottobre 2022 (appartenenze chiuse prima del 1/11/2022: Misto provvisorio "
                         "prima della costituzione dei gruppi). La nascita di un gruppo nuovo (es. IV-CR alla Camera) conta come "
                         "cambio; un ritorno al gruppo di prima conta come un nuovo cambio. Data = inizio dell'appartenenza nuova. "
                         "Fonte: appartenenze ai gruppi dell'anagrafica dei due rami.",
            "by_chamber": {k: {"persons": len(v["persons"]), "changes": v["changes"]} for k, v in per_ramo.items()}} | pagina
