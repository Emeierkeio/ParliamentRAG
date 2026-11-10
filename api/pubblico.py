"""Gli strumenti pubblici del server MCP di produzione (mcp.parliamentrag.it) sul Postgres v3: stessi nomi, stessi
argomenti, stessi campi nelle risposte, perché i client già collegati (connettore di claude.ai, ChatGPT, Claude Desktop)
continuino a funzionare dopo il cambio di DNS. In entrata valgono gli id vecchi (leg19_sed736, camera_leg19_sed734_v001)
e gli uri v3; in uscita si danno gli id vecchi. Quello che v3 non sa calcolare resta null o vuoto, mai inventato."""

from __future__ import annotations

import datetime as dt
import json
import re

import psycopg
from pydantic import Field

from pipeline.ambiente import env

from .registro import Parametri, Strumento
from .strumenti import agenda, atti, citazioni, comune, emendamenti, ricerca, voti
from .strumenti.comune import LEGISLATURA, brevi


class NonTrovato(LookupError):
    """Id che non corrisponde a niente: al client arriva come risultato con isError."""


# ---------- id vecchi ↔ uri v3 ----------

_URI = re.compile(r"it:(camera|senato):(\d+):sed(\d+)(?::(.+))?$")
_VOTO = re.compile(r"(camera|senato)_leg(\d+)_sed(\d+)_v(\d+)$")
_SEDUTA = re.compile(r"(sen_)?leg(\d+)_sed(\d+)(?:_(.+))?$")


def cognome_da_etichetta(etichetta: str | None) -> str | None:
    """Il cognome scritto nel resoconto prima della carica («CALDERONE, ministro del lavoro…» → «Calderone»): per i
    membri del governo che non sono parlamentari, la cui scheda nel v3 non ha il nome."""
    nome = (etichetta or "").split(",")[0].strip()
    return nome.title() if nome else None


def id_vecchio(uri: str) -> str:
    """Uri v3 di seduta, punto all'ordine del giorno o votazione d'Aula → id del server di produzione. Il resto passa
    com'è. Seduta: leg19_sed736 / sen_leg19_sed469; voto: camera_leg19_sed734_v001 (seduta su tre cifre, come in
    produzione); punto: leg19_sed736_tit00010 / sen_leg19_sed469_d-d1e36."""
    m = _URI.match(uri or "")
    if not m:
        return uri
    ramo, leg, sed, resto = m.groups()
    n, pre = int(sed), "" if ramo == "camera" else "sen_"
    if resto is None:
        return f"{pre}leg{leg}_sed{n}"
    v = re.fullmatch(r"v(\d+)", resto)
    if v:
        return f"{ramo}_leg{leg}_sed{n:03d}_v{int(v.group(1)):03d}"
    return f"{pre}leg{leg}_sed{n}_{resto}"


def uri_v3(ident: str) -> str | None:
    """Id vecchio o uri v3 → uri v3 (seduta su quattro cifre, voto su tre). None se il formato non è noto. I dibattiti
    vecchi del Senato (sen_leg19_sed470_<titolo_in_slug>) diventano un uri che non esiste: li risolve get_debate."""
    ident = (ident or "").strip()
    if _URI.match(ident):
        return ident
    m = _VOTO.match(ident)
    if m:
        ramo, leg, sed, v = m.groups()
        return f"it:{ramo}:{leg}:sed{int(sed):04d}:v{int(v):03d}"
    m = _SEDUTA.match(ident)
    if m:
        sen, leg, sed, resto = m.groups()
        base = f"it:{'senato' if sen else 'camera'}:{leg}:sed{int(sed):04d}"
        return base if resto is None else f"{base}:{resto}"
    return None


# ---------- pezzi comuni ----------

MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
        "novembre", "dicembre")
PRESIEDE = ("PRESIDENTE", "senatore", "")          # as_office che non sono un ruolo da mostrare
GOVERNO = re.compile(r"^(ministr|sottosegretari|vice ?ministr|presidente del consiglio|vice ?presidente del consiglio)", re.I)

# Messo nei risultati che restituiscono interventi, come in produzione: il modello legge i risultati più delle istruzioni.
VERIFICA_DOPO = ("Before you reply about what deputies or senators said: quote them verbatim in «…» with the speaker's name "
                 "nearby and the link to the record, and give the position of every group, the Mixed Group by component.")
NOTA_LEGGE = ("An act that became law carries `law`: `label` (e.g. \"Legge n. 180 del 9 ottobre 2026\"), Gazzetta Ufficiale "
              "number and date, and `eli`, the Normattiva page of the law. When you say an act became law, give the label "
              "and cite the `eli` link. Without `law`, the data do not link the act to a published law.")


def _ramo(chamber: str | None) -> str | None:
    return chamber if chamber in ("camera", "senato") else None


def _taglia(t: str | None, n: int = 600) -> str | None:
    if t and len(t) > n:
        return t[:n].rsplit(" ", 1)[0] + "…"
    return t


def _data_it(d: dt.date) -> str:
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


def _https(url: str | None) -> str | None:
    if url and re.match(r"http://[\w.-]*(camera|senato)\.it/", url):
        return "https://" + url[7:]
    return url


def _data(s: str | None) -> dt.date | None:
    """Date ISO come in produzione (stringhe); una data non valida si ignora invece di far fallire la chiamata."""
    try:
        return dt.date.fromisoformat(s[:10]) if s else None
    except ValueError:
        return None


def url_intervento(uri: str | None, record_url: str | None = None) -> str | None:
    """Pagina del resoconto: per la Camera lo stenografico con l'ancora dell'intervento, per il Senato la pagina della
    seduta (sitting.record_url) se c'è (strumenti/comune.url_intervento)."""
    return comune.url_intervento(uri, record_url)


def _titolo_nome(given: str | None, family: str | None, etichetta: str | None) -> str:
    nome = " ".join(x for x in (given, family) if x)
    return nome or (etichetta or "").title()


def _legge(r: dict) -> dict | None:
    if not r.get("law_number"):
        return None
    etichetta = f"Legge n. {r['law_number']}" + (f" del {_data_it(r['law_date'])}" if r.get("law_date") else "")
    # v3 non ha ancora Gazzetta Ufficiale né il link Normattiva della legge: restano null
    return {"kind": "legge", "number": r["law_number"], "date": str(r["law_date"]) if r.get("law_date") else None,
            "label": etichetta, "eli": None, "normattiva_url": None, "gu_number": None, "gu_date": None, "title": None}


def _schede_atti(c: psycopg.Connection, uris: list[str]) -> dict[str, dict]:
    """Gli atti come in produzione (uri, title, subject, number, status, url, text_url, law). `subject` (di cosa parla una
    mozione) v3 non lo ha: null."""
    uris = sorted({u for u in uris if u})
    if not uris:
        return {}
    righe = c.execute("""SELECT uri, number, title, status, card_url, text_urls, law_number, law_date FROM act
                         WHERE uri = ANY(%s)""", (uris,)).fetchall()
    return {r["uri"]: {"uri": r["uri"], "title": r["title"], "subject": None, "number": r["number"], "status": r["status"],
                       "url": _https(r["card_url"]), "text_url": _https(r["text_urls"][-1]) if r["text_urls"] else None,
                       "law": _legge(r)} for r in righe}


def _nota_legge(schede: list[dict]) -> dict:
    return {"law_note": NOTA_LEGGE} if any(a.get("law") for a in schede) else {}


# ---------- votazioni ----------

SQL_VOTI = """SELECT v.uri, v.sitting, v.chamber, v.number, v.date, nullif(btrim(v.title), '') AS title, v.description, v.kind, v.favor, v.against,
       v.abstain, v.present, v.majority, v.approved, v.secret, v.final,
       (SELECT min(x.act) FROM vote_act x WHERE x.vote = v.uri) AS atto
FROM vote v"""
DDL = re.compile(r"\bDDL\s+(?:n\.\s*)?(\d+)", re.I)
SEGUITO = re.compile(r"^(EM|ART|SUBEM)\b", re.I)            # «EM 1.2»: il progetto di legge è quello delle votazioni prima


def _numero_legale(v: dict) -> bool:
    return (v.get("title") or "").lower().startswith("verifica del numero legale")


def _esito(v: dict) -> str | None:
    if _numero_legale(v) or v["approved"] is None:
        return None
    return "approved" if v["approved"] else "rejected"


def _atto_da_descrizione(c: psycopg.Connection, ramo: str, descrizione: str | None) -> str | None:
    m = DDL.search(descrizione or "")
    if not m:
        return None
    r = c.execute("SELECT uri FROM act WHERE chamber = %s AND legislature = %s AND kind = 'bill' AND number = %s",
                  (ramo, LEGISLATURA, m.group(1))).fetchone()
    return r["uri"] if r else None


def _atto_del_voto(c: psycopg.Connection, v: dict) -> str | None:
    """L'atto votato: da vote_act; alla Camera, se manca, dal «DDL 2700-A» della descrizione o, per «EM 1.2» e simili,
    dall'ultima votazione precedente della seduta che lo nomina (lo fa anche la produzione)."""
    if v["atto"]:
        return v["atto"]
    if v["chamber"] != "camera":
        return None
    a = _atto_da_descrizione(c, "camera", v["description"])
    if a or not SEGUITO.match(v["description"] or ""):
        return a
    for r in c.execute("SELECT description FROM vote WHERE sitting = %s AND number < %s ORDER BY number DESC",
                       (v["sitting"], v["number"])):
        if DDL.search(r["description"] or ""):
            return _atto_da_descrizione(c, "camera", r["description"])
        if not SEGUITO.match(r["description"] or ""):
            return None
    return None


def _descrizione(v: dict, atto: dict | None) -> str | None:
    if _numero_legale(v):
        return f"Verifica del numero legale: conta i presenti, non è una votazione su un atto (presenti {v['present']})"
    if v["description"]:
        return v["description"]
    if v["chamber"] == "senato" and atto:                # al Senato la descrizione nomina il disegno di legge
        return f"Ddl n. {atto['number']}: {atto['title']}"
    return None


def _voto_in_elenco(v: dict, atto: dict | None) -> dict:
    out = {"id": id_vecchio(v["uri"]), "number": v["number"], "subject": v["title"], "description": _descrizione(v, atto),
           "final_vote": bool(v["final"]), "outcome": _esito(v), "in_favor": v["favor"], "against": v["against"],
           "abstained": v["abstain"], "act_subject": None}
    if atto:
        out.update(act_number=atto["number"], act_title=atto["title"])
    if _numero_legale(v):
        out["kind"] = "quorum_check"
    return out


def _voto(c: psycopg.Connection, vote_id: str) -> dict:
    uri = uri_v3(vote_id)
    v = c.execute(SQL_VOTI + " WHERE v.uri = %s", (uri,)).fetchone() if uri else None
    if not v:
        raise NonTrovato(f"vote not found: {vote_id}")
    return v


def _per_gruppo(c: psycopg.Connection, v: dict) -> list[dict]:
    """Il voto dei gruppi da votazione(), il Misto per componente. `absent` comprende missioni, presidenza e presenti non
    votanti; `secret` conta chi ha votato a scrutinio segreto (scelta non pubblica)."""
    vz = voti.votazione(c, v["uri"], with_ballots=False)
    out = []
    for g in vz.groups if vz else []:
        segreto = g.other if v["secret"] else 0
        out.append({"party": g.group.name if g.group else None, "favor": g.favor, "against": g.against, "abstain": g.abstain,
                    "absent": g.absent + g.mission + g.other - segreto, "secret": segreto})
    return out


def coerenza(v: dict, gruppi: list[dict]) -> dict | None:
    """Totali ufficiali contro somma dei gruppi, come `_counts_consistency` della produzione."""
    if v["secret"]:
        return {"applicable": False,
                "reason": "Secret ballot: individual expressions are not public, so per-group counts cannot be compared "
                          "with the official totals."}
    if not gruppi:
        return None
    somme = {"in_favor": sum(g["favor"] for g in gruppi), "against": sum(g["against"] for g in gruppi),
             "abstained": sum(g["abstain"] for g in gruppi)}
    ufficiali = {"in_favor": v["favor"], "against": v["against"], "abstained": v["abstain"]}
    out = {"official_totals": ufficiali, "sum_of_group_breakdown": somme,
           "consistent": all(ufficiali[k] is None or ufficiali[k] == somme[k] for k in somme)}
    if not out["consistent"]:
        out["note"] = ("Official aggregate totals and the sum of per-group counts disagree. Both come from the official "
                       "record; cite one explicitly instead of mixing them.")
    return out


def _singoli(c: psycopg.Connection, v: dict) -> list[dict]:
    # il gruppo come in voti.votazione: quello scritto nel voto, poi grp_alias, poi il gruppo della persona alla data
    righe = c.execute("""
        SELECT b.person, b.result, p.given_name, p.family_name, g.name AS gruppo, g.short_name
        FROM ballot b JOIN vote v ON v.uri = b.vote JOIN person p ON p.uri = b.person
        LEFT JOIN grp g ON g.uri = coalesce((SELECT uri FROM grp WHERE uri = b.grp), (SELECT grp FROM grp_alias WHERE alias = b.grp),
                                              group_at(b.person, v.date))
        WHERE b.vote = %s ORDER BY p.family_name, p.given_name""", (v["uri"],)).fetchall()
    return [{"id": r["person"], "first_name": r["given_name"], "last_name": r["family_name"], "party": r["gruppo"],
             "outcome": r["result"],
             "senato_id": r["person"].rsplit(":", 1)[-1] if r["person"].startswith("it:person:senato:") else None,
             "_sigla": r["short_name"]} for r in righe]


# ---------- parametri (nomi e predefiniti della produzione) ----------

Ramo = Field("both", description='"both" (default), "camera" (Chamber of Deputies) or "senato" (Senate).')


class SearchParliament(Parametri):
    query: str = Field(description="Search query, ideally in Italian.")
    doc_type: str = Field("all", description='"all", "speech" (floor speeches) or "act" (parliamentary acts).')
    group: str | None = Field(None, description='Optional parliamentary group name filter (e.g. "MOVIMENTO 5 STELLE").')
    start_date: str | None = Field(None, description="Optional YYYY-MM-DD lower bound.")
    end_date: str | None = Field(None, description="Optional YYYY-MM-DD upper bound.")
    max_results: int = Field(10, description="How many results to return (1-30).")
    chamber: str = Ramo


class VerifyAnswer(Parametri):
    answer: str = Field(description="The full answer, quotes in «…» with the speaker's name nearby.")
    question: str | None = Field(None, description="The user's question; it sets the topic for authority.")
    chamber: str = Field("both", description='"both" (default), "camera" or "senato": the houses the answer is about.')


class ListSessions(Parametri):
    limit: int = Field(10, description="Sittings per page (1-30).")
    before: str | None = Field(None, description="ISO date cursor for pagination (returns sittings before it).")
    search: str | None = Field(None, description="Optional words to find in debate titles (plurals fold).")
    from_date: str | None = Field(None, description="Optional YYYY-MM-DD lower bound.")
    to_date: str | None = Field(None, description="Optional YYYY-MM-DD upper bound.")
    chamber: str = Field("both", description='"both" (default), "camera" or "senato".')
    session_id: str | None = Field(None, description='Optional: only this sitting (e.g. "leg19_sed148", "sen_leg19_sed469").')


class ParliamentAgenda(Parametri):
    start_date: str = Field(description="First day, YYYY-MM-DD.")
    end_date: str | None = Field(None, description="Last day, YYYY-MM-DD (at most 62 days after start_date); default: start_date.")
    chamber: str = Field("both", description='"both" (default), "camera" or "senato".')
    types: list[str] | None = Field(None, description='Which events (default all): "aula" (plenary sittings, planned and held; a day with status "calendar" comes from the calendar of works of the Chamber and has no sitting number yet), '
                                    '"commissioni" (committee sittings held and, from today on, committee convocations with status "convened": times, venue, items and hearings), "termini" (amendment deadlines), "pareri" (deadlines for committee opinions on '
                                    'government acts such as draft legislative decrees, and on appointments; Chamber only), "atti" (bills filed), '
                                    '"voti" (final votes), "leggi" (laws published).')


class SearchAmendments(Parametri):
    text: str | None = Field(None, max_length=6000, description="A topic, a sentence or the text of a draft amendment, in Italian: "
                             "finds amendments with similar meaning across the legislature, closest first.")
    query: str | None = Field(None, description="Words in the amendment text (Italian; \"quoted phrase\", -word, or).")
    bill: str | None = Field(None, description='Bill, as "C. 2750", "S. 1689" or an act uri; empty: the whole legislature.')
    number: str | None = Field(None, description='Amendment number as written by the source ("1.1", "2.0.3").')
    chamber: str = Field("both", description='"both" (default), "camera" or "senato".')
    group: str | None = Field(None, description="Parliamentary group of a signatory on that day (name or abbreviation).")
    outcome: str | None = Field(None, description="Computed outcome code, as in the `esito` field of the results.")
    start_date: str | None = Field(None, description="YYYY-MM-DD lower bound of the date.")
    end_date: str | None = Field(None, description="YYYY-MM-DD upper bound of the date.")
    max_results: int = Field(20, ge=1, le=50)


class AmendmentId(Parametri):
    amendment_id: str = Field(description="Amendment uri from search_amendments (e.g. \"it:camera:19:ac:2750:eme:ass588:1.1\").")


class SessionId(Parametri):
    session_id: str = Field(description='Session id from list_sessions (e.g. "leg19_sed700").')


class VoteDetails(Parametri):
    vote_id: str = Field(description="Vote id from get_session_votes.")
    include_individual_votes: bool = Field(False, description="Return the full per-member list (large).")
    deputy: str | None = Field(None, description="Return only individual votes of members whose name contains this string "
                                                 "(case-insensitive). Overrides include_individual_votes.")
    group: str | None = Field(None, description="Return only individual votes of this parliamentary group (substring match). "
                                                "Overrides include_individual_votes.")


class VoteId(Parametri):
    vote_id: str = Field(description="Vote id from get_session_votes.")


class DebateId(Parametri):
    debate_id: str = Field(description="Debate id from list_sessions.")


class Hemicycle(Parametri):
    vote_id: str = Field(description="Vote id from get_session_votes.")
    format: str = Field("png", description='"png" (default) or "svg"; accepted for compatibility, no chart is drawn.')


# ---------- search_parliament ----------

def _norm(t: str) -> str:
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip().lower()


def _frase(q: str) -> str:
    """La frase da cercare tale e quale: il testo fra virgolette, se c'è, se no la domanda senza operatori."""
    m = re.search(r'"([^"]+)"', q)
    return _norm(m.group(1) if m else re.sub(r"(^|\s)-\S+|\bor\b", " ", q))


def _estratto(testo: str, frase: str, n: int = 600) -> str:
    k = _norm(testo).find(frase) if frase else -1
    if k <= 150:                                         # _norm accorcia solo gli spazi: la posizione è vicina a quella vera
        return _taglia(testo, n)
    da = testo.find(" ", k - 150) + 1
    return "…" + _taglia(testo[da:], n)


def _passa_gruppo(nome: str | None, sigla: str | None, filtro: str | None) -> bool:
    if not filtro:
        return True
    f = filtro.lower()
    return any(f in (x or "").lower() or (x and x.lower() in f) for x in (nome, sigla))


def _membri_governo(c: psycopg.Connection, persone: list[str], d: dt.date) -> dict[str, str]:
    """Persona → carica di governo alla data (testo della fonte, se c'è)."""
    if not persone:
        return {}
    righe = c.execute("""SELECT o.person, coalesce(o.title_raw, o.title) AS carica FROM office o
                         WHERE o.person = ANY(%s) AND o.target LIKE 'it:gov:%%' AND o.start_date <= %s
                           AND (o.end_date IS NULL OR o.end_date >= %s) ORDER BY o.start_date""", (persone, d, d)).fetchall()
    return {r["person"]: r["carica"] for r in righe}


def _cerca_interventi(c, p: SearchParliament, ramo, dal, al, quanti) -> tuple[int, list[dict]]:
    colpi = ricerca.cerca_interventi(c, p.query, ramo, None, dal, al, include_summaries=False, limit=50 if p.group else quanti)
    if not colpi:
        return 0, []
    dettagli = {r["uri"]: r for r in c.execute("""
        SELECT s.uri, s.text, s.speaker_label, s.as_group, s.as_office, p.given_name, p.family_name, s.person
        FROM speech s LEFT JOIN person p ON p.uri = s.person WHERE s.uri = ANY(%s)""", ([h.uri for h in colpi],))}
    frase, out = _frase(p.query), []
    link = comune.url_interventi(c, [h.uri for h in colpi])
    for h in colpi:
        d = dettagli[h.uri]
        g = h.person.group if h.person else None
        governo = bool(GOVERNO.match(d["as_office"] or "")) or (not d["as_group"] and d["person"] in
                                                                  _membri_governo(c, [d["person"]], h.sitting.date))
        gruppo = "Governo" if governo else (g.name if g else d["as_group"])
        if not _passa_gruppo(gruppo, g.short_name if g else d["as_group"], p.group):
            continue
        out.append({"type": "speech", "id": id_vecchio(h.uri), "chamber": h.sitting.chamber, "url": link.get(h.uri),
                    # il testo v3 comincia dopo il nome di chi parla («, Sottosegretario…»): il nome si rimette davanti
                    "text": _estratto((d["speaker_label"] or "") + d["text"] if d["text"].startswith(",") else d["text"], frase), "date": str(h.sitting.date), "session_number": h.sitting.number,
                    "debate_title": h.item_title, "first_name": d["given_name"],
                    "last_name": d["family_name"] or (None if d["given_name"] else cognome_da_etichetta(d["speaker_label"])),
                    "group": gruppo, "score": None, "match_type": "keyword", "is_exact": bool(frase) and frase in _norm(d["text"])})
    # il totale: quanti interventi d'Aula e di commissione (riassunti esclusi) contengono le parole, con gli stessi filtri
    totale = c.execute("""
        SELECT count(*) AS n FROM speech s JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
        WHERE to_tsvector('italian', s.text) @@ websearch_to_tsquery('italian', %(q)s) AND s.kind IS DISTINCT FROM 'summary'
          AND (%(ramo)s::text IS NULL OR st.chamber = %(ramo)s)
          AND (%(dal)s::date IS NULL OR st.date >= %(dal)s) AND (%(al)s::date IS NULL OR st.date <= %(al)s)""",
        {"q": p.query, "ramo": ramo, "dal": dal, "al": al}).fetchone()["n"]
    return (len(out) if p.group else totale), out[:quanti]


def _cerca_atti(c, p: SearchParliament, ramo, dal, al, quanti) -> tuple[int, list[dict]]:
    filtrato = bool(p.group or dal or al)
    totale, xs = atti.cerca_atti(c, p.query, ramo, limit=100 if filtrato else quanti)
    xs = [a for a in xs if (not dal or (a.date and a.date >= dal)) and (not al or (a.date and a.date <= al))]
    if not xs:
        return (0 if filtrato else totale), []
    uris = [a.uri for a in xs]
    extra = {r["uri"]: r for r in c.execute("SELECT uri, kind_raw, text, description FROM act WHERE uri = ANY(%s)", (uris,))}
    primi = {r["act"]: r["person"] for r in c.execute(
        "SELECT DISTINCT ON (act) act, person FROM act_sponsor WHERE act = ANY(%s) AND first ORDER BY act, person", (uris,))}
    nomi = {r["uri"]: r for r in c.execute("SELECT uri, given_name, family_name FROM person WHERE uri = ANY(%s)",
                                           (list(primi.values()),))}
    persone = brevi(c, list(primi.values()))
    frase, out = _frase(p.query), []
    for a in xs:
        e, chi = extra[a.uri], primi.get(a.uri)
        pb, n = persone.get(chi), nomi.get(chi) or {}
        gruppo = pb.group.name if pb and pb.group else None
        if not _passa_gruppo(gruppo, pb.group.short_name if pb and pb.group else None, p.group):
            continue
        testo = e["text"] or e["description"] or a.title or ""
        out.append({"type": "act", "id": a.uri, "text": _estratto(testo, frase), "date": str(a.date) if a.date else None,
                    "first_name": n.get("given_name"), "last_name": n.get("family_name"), "group": gruppo,
                    "act_type": (e["kind_raw"] or "").upper() or None, "act_kind": a.kind, "act_title": a.title,
                    "act_number": a.number, "score": None, "match_type": "keyword",
                    "is_exact": bool(frase) and frase in _norm(f"{a.title or ''} {testo}"), "chamber": a.chamber,
                    "url": _https(a.card_url)})
    return (len(out) if filtrato else totale), out[:quanti]


def search_parliament(c: psycopg.Connection, p: SearchParliament) -> dict:
    """Ricerca per parole (v3 non ha ancora gli embedding): interventi con cerca_interventi, atti con cerca_atti sul
    titolo. `score` è null, `match_type` «keyword», `is_exact` vero se la frase c'è tale e quale."""
    quanti, ramo = max(1, min(p.max_results, 30)), _ramo(p.chamber)
    dal, al = _data(p.start_date), _data(p.end_date)
    n_i, interventi = _cerca_interventi(c, p, ramo, dal, al, quanti) if p.doc_type in ("all", "speech") else (0, [])
    n_a, schede = _cerca_atti(c, p, ramo, dal, al, quanti) if p.doc_type in ("all", "act") else (0, [])
    risultati = []                                       # alternati, così con «all» si vedono entrambi i tipi
    for i in range(quanti):
        risultati += [x[i] for x in (interventi, schede) if i < len(x)]
    risultati = risultati[:quanti]
    return {"total": n_i + n_a, "results": risultati, "next_step": VERIFICA_DOPO}


# ---------- verify_answer ----------

SEGNI = {"pass": "✅", "warn": "⚠️", "fail": "❌", "na": "➖"}
SIGNIFICATI = {"exact": "verbatim in the record",
               "omissions": "pieces are in the record but words between them were cut",
               "modified": "not verbatim; closest_passage is what was actually said",
               "not_found": "not in any floor speech of the Chamber or the Senate in the 19th legislature"}
CHIUSURA = ("Checked by ParliamentRAG, a research project that checks answers about the Italian Parliament against official "
            "data, without an AI model. Check any answer at www.parliamentrag.it/verifica")
AMBITI = {"camera": "Camera dei deputati, XIX legislatura", "senato": "Senato della Repubblica, XIX legislatura"}


def _citazioni(c: psycopg.Connection, risposta: str) -> list[dict]:
    """Le citazioni tra «…» con verifica_citazioni, nella forma della produzione. «modified» (con il passo più vicino) v3
    non lo calcola: una citazione non trovata è «not_found»."""
    v = citazioni.verifica(c, risposta)
    link = comune.url_interventi(c, [e["speech"] for e in v["results"] if e.get("found")])
    out = []
    for e in v["results"]:
        q = e["quote"]
        item = {"quote": _taglia(q, 200), "status": "not_found"}
        if e["found"]:
            item["status"] = "omissions" if citazioni.PARTI.search(q) else "exact"
            k = risposta.find(q)
            vicino = risposta[max(0, k - 250):k + len(q) + 250].lower()
            cognome = (e["speaker"] or "").split(" ", 1)[-1].lower()
            item.update(speaker=e["speaker"], group=e["group"], date=e["date"], record_url=link.get(e["speech"]),
                        speaker_named_nearby=bool(cognome) and cognome in vicino)
        out.append(item)
    return out


def _riga_citazioni(cs: list[dict]) -> tuple[str, str]:
    if not cs:
        return "na", "no quotes in «…» to check"
    esatte = sum(x["status"] == "exact" for x in cs)
    problemi = [x for x in cs if x["status"] != "exact" or not x.get("speaker_named_nearby")]
    testo = f"{esatte}/{len(cs)} verbatim in the parliamentary record"
    if problemi:
        nomi = {"omissions": "words cut", "not_found": "not in the record"}
        testo += " — " + "; ".join(f"«{_taglia(x['quote'], 60)}» " + (nomi.get(x["status"]) or "speaker not named nearby")
                                   for x in problemi)
    esito = "pass" if not problemi else ("fail" if any(x["status"] == "not_found" for x in cs) else "warn")
    return esito, testo


def _gruppi_autorevolezza(c: psycopg.Connection, risposta: str, domanda: str | None, rami: list[str]) -> dict | None:
    """Gruppi e autorevolezza calcolati su Postgres (fascicolo/verifica.py), nella forma {summary, groups, authority,
    scope}. None se il controllo non si può fare: le due righe dicono che non è disponibile."""
    from .fascicolo import verifica
    try:
        return verifica.verifica(c, risposta, domanda, rami)
    except psycopg.Error:
        return None


def _riga_gruppi(g: dict) -> str:
    testo = f"{g['named']}/{g['total']} groups, Mixed Group components and Government present"
    mancanti = [x["key"] for x in g["items"] if x["status"] == "missing"]
    muti = [x["key"] for x in g["items"] if x["status"] == "silent"]
    if mancanti:
        testo += " — missing: " + ", ".join(mancanti)
    if muti:
        testo += " — no speeches on the topic: " + ", ".join(muti)
    for m in g.get("mismatches", []):
        testo += f" — {m['name']} is written as ({m['group_written']}) but belongs to {m.get('voice') or m.get('group')}"
    return testo


def _riga_autorevolezza(a: dict) -> str:
    voci = a["voices"]
    if not a["available"]:
        return "authority on the topic could not be computed"
    if not voci:
        return "no deputy, senator or member of the Government quoted or named"

    def perche(v: dict) -> str:
        if v.get("role") == "governo":
            return "Government"
        if v.get("role") == "relatore":
            return "rapporteur"
        if v.get("on_topic") is False:
            return "did not speak on the topic"
        if not v.get("rank"):
            return "not ranked"
        n = v.get("pool_size", v.get("group_size"))
        if v.get("pool") == "speakers_on_topic":
            return f"{v['rank']}/{n} among those in the group who spoke on the topic"
        return f"{v['rank']}/{n} in group"
    ok = sum(1 for v in voci if v["authoritative"])
    return (f"{ok}/{len(voci)} authoritative (Government, rapporteur or top 5 of their group among those who spoke on the "
            "topic): ") + "; ".join(f"{v['name']} {perche(v)}" + (" (named)" if v.get("source") == "named" else "") for v in voci)


def verify_answer(c: psycopg.Connection, p: VerifyAnswer) -> dict:
    """Le tre garanzie, per la verifica del sito (non è uno strumento MCP). Citazioni: verifica_citazioni. Gruppi e
    autorevolezza: _gruppi_autorevolezza; se manca, le due righe dicono che il controllo non è disponibile."""
    risposta = p.answer[:20000]
    rami = {"camera": ["camera"], "senato": ["senato"]}.get(p.chamber, ["camera", "senato"])
    cs = _citazioni(c, risposta)
    esito_q, riga_q = _riga_citazioni(cs)
    f = _gruppi_autorevolezza(c, risposta, p.question, rami)
    if f is None:
        esiti = {"groups": "na", "authority": "na", "quotes": esito_q}
        gruppi = {"items": [], "mismatches": []}
        autorevolezza = {"topic": p.question, "available": False, "voices": []}
        righe = ["All groups: not checked (not available yet)",
                 "Authoritative voices: not checked (not available yet)"]
        ambito = ", ".join(AMBITI[r] for r in rami)
    else:
        esiti = {"groups": f["summary"]["groups"], "authority": f["summary"]["authority"], "quotes": esito_q}
        gruppi, autorevolezza, ambito = f["groups"], f["authority"], f.get("scope")
        righe = ["All groups: " + _riga_gruppi(gruppi), "Authoritative voices: " + _riga_autorevolezza(autorevolezza)]
    voci = gruppi["items"]
    return {
        "verdict": [f"{SEGNI[esiti['groups']]} {righe[0]}", f"{SEGNI[esiti['authority']]} {righe[1]}",
                    f"{SEGNI[esito_q]} Exact quotes: {riga_q}", CHIUSURA],
        "scope": ambito,
        "outcome": esiti,
        "groups": {"present": [g["key"] for g in voci if g["status"] not in ("missing", "silent")],
                   "missing": [g["label"] for g in voci if g["status"] == "missing"],
                   "silent": [g["label"] for g in voci if g["status"] == "silent"]},
        "groups_detail": [{k: g.get(k) for k in ("key", "label", "status")} for g in voci],
        "group_mismatches": [{k: m.get(k) for k in ("name", "group_written", "voice", "group")} for m in gruppi.get("mismatches", [])],
        "authority": {"topic": autorevolezza.get("topic"), "available": autorevolezza.get("available", False),
                      "voices": [{k: v[k] for k in ("name", "group", "role", "rank", "pool_size", "group_size", "pool", "on_topic",
                                                   "authoritative", "source") if k in v} for v in autorevolezza.get("voices", [])]},
        "quotes": cs,
        "status_meaning": SIGNIFICATI,
        "verify_page": "https://www.parliamentrag.it/",
    }


# ---------- sedute e dibattiti ----------

SQL_PUNTI = """SELECT i.sitting, i.uri, i.ord, i.title, i.procedural,
       (SELECT array_agg(a.number ORDER BY x.act_ref) FROM agenda_item_act x JOIN act a ON a.uri = x.act WHERE x.item = i.uri) AS numeri
FROM agenda_item i"""
TRONCO = re.compile(r"\s*(\bnn?\.|:)\s*$")


def _titolo(r: dict) -> str:
    """Il titolo del punto. Al Senato l'intestazione si ferma prima dei numeri («… del disegno di legge:»): si completa con
    i numeri degli atti collegati, come «…: (1804)» nei titoli della produzione."""
    t = (r["title"] or "").strip()
    n = r.get("numeri")
    if n and TRONCO.search(t):
        return f"{TRONCO.sub('', t)}: ({n[0] if len(n) == 1 else ', '.join(n[:-1]) + ' e ' + n[-1]})"
    return t

def _riassunto(d: dt.date, titoli: list[str]) -> str | None:
    """Al posto del riassunto scritto da un modello in produzione: una riga fissa con i titoli dei punti non procedurali,
    senza modello."""
    visti: list[str] = []
    for t in titoli:
        t = t.strip().rstrip(".:").strip()
        t = t[:1].lower() + t[1:]
        if t and t not in visti:
            visti.append(t)
    if not visti:
        return None
    return _taglia(f"Nella seduta del {_data_it(d)} sono stati trattati i seguenti argomenti: {'; '.join(visti)}.", 800)


def list_sessions(c: psycopg.Connection, p: ListSessions) -> dict:
    """Sedute d'Aula tenute, dalla più recente. `search`: parole nei titoli dei punti all'ordine del giorno."""
    quante = max(1, min(p.limit, 30))
    righe = c.execute("""
        SELECT s.uri, s.chamber, s.number, s.date,
               (SELECT count(*) FROM vote v WHERE v.sitting = s.uri) AS voti,
               (SELECT count(*) FROM speech x JOIN agenda_item i ON i.uri = x.item
                WHERE i.sitting = s.uri AND x.as_office IS DISTINCT FROM 'PRESIDENTE') AS interventi
        FROM sitting s
        WHERE s.body LIKE '%%:aula' AND s.status = 'held' AND (%(ramo)s::text IS NULL OR s.chamber = %(ramo)s)
          AND (%(prima)s::date IS NULL OR s.date < %(prima)s)
          AND (%(dal)s::date IS NULL OR s.date >= %(dal)s) AND (%(al)s::date IS NULL OR s.date <= %(al)s)
          AND (%(sed)s::text IS NULL OR s.uri = %(sed)s)
          AND (%(q)s::text IS NULL OR EXISTS (SELECT 1 FROM agenda_item i WHERE i.sitting = s.uri
               AND to_tsvector('italian', coalesce(i.title, '')) @@ websearch_to_tsquery('italian', %(q)s)))
        ORDER BY s.date DESC, s.chamber, s.number DESC LIMIT %(lim)s""",
        {"ramo": _ramo(p.chamber), "prima": _data(p.before), "dal": _data(p.from_date), "al": _data(p.to_date),
         "q": p.search or None, "sed": (uri_v3(p.session_id) or "-") if p.session_id else None, "lim": quante + 1}).fetchall()
    altre, righe = len(righe) > quante, righe[:quante]
    punti: dict[str, list[dict]] = {}
    for r in c.execute(SQL_PUNTI + " WHERE i.sitting = ANY(%s) AND coalesce(i.title, '') <> '' ORDER BY i.sitting, i.ord",
                       ([r["uri"] for r in righe],)):
        punti.setdefault(r["sitting"], []).append({**r, "title": _titolo(r)})
    sedute = [{"id": id_vecchio(s["uri"]), "chamber": s["chamber"], "number": s["number"], "date": str(s["date"]),
               "recap": _riassunto(s["date"], [x["title"] for x in punti.get(s["uri"], []) if not x["procedural"]]),
               "vote_count": s["voti"], "speech_count": s["interventi"],
               "debates": [{"id": id_vecchio(x["uri"]), "title": _taglia(x["title"], 200)} for x in punti.get(s["uri"], [])]}
              for s in righe]
    return {"sessions": sedute, "next_cursor": sedute[-1]["date"] if sedute else None, "has_more": altre}


def get_session_votes(c: psycopg.Connection, p: SessionId) -> dict:
    uri = uri_v3(p.session_id)
    if not uri or not c.execute("SELECT 1 FROM sitting WHERE uri = %s", (uri,)).fetchone():
        raise NonTrovato(f"session not found: {p.session_id}")
    vs = c.execute(SQL_VOTI + " WHERE v.sitting = %s ORDER BY v.number", (uri,)).fetchall()
    # l'atto di «EM 1.2» è quello dell'ultimo «DDL …» della seduta: si porta avanti qui, senza rileggere i voti
    ultimo, scelti = None, []
    for v in vs:
        a = v["atto"] or (_atto_da_descrizione(c, "camera", v["description"]) if v["chamber"] == "camera" else None)
        if a is None and v["chamber"] == "camera" and SEGUITO.match(v["description"] or ""):
            a = ultimo
        ultimo = a if (a or not SEGUITO.match(v["description"] or "")) else ultimo
        scelti.append(a)
    schede = _schede_atti(c, scelti)
    return {"session_id": p.session_id, "votes": [_voto_in_elenco(v, schede.get(a)) for v, a in zip(vs, scelti)]}


def _slug(t: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", t).strip("_").lower()


def _punto(c: psycopg.Connection, debate_id: str) -> dict:
    uri = uri_v3(debate_id)
    if not uri:
        raise NonTrovato(f"debate not found: {debate_id}")
    r = c.execute(SQL_PUNTI + " WHERE i.uri = %s", (uri,)).fetchone()
    m = _URI.match(uri)
    if r is None and m and m.group(1) == "senato" and m.group(4):
        # id vecchio del Senato: il titolo in slug. Vale il punto della seduta il cui titolo completo, in slug, è l'inizio
        # dell'id: il più lungo, a pari lunghezza il primo (le «Ripresa della discussione…» ripetute)
        seduta, resto = uri.rsplit(":", 1)[0], m.group(4)
        candidati = [(len(_slug(_titolo(x))), -x["ord"], x) for x in c.execute(
            SQL_PUNTI + " WHERE i.sitting = %s AND coalesce(i.title, '') <> ''", (seduta,))
            if _slug(_titolo(x)) and resto.startswith(_slug(_titolo(x)))]
        r = max(candidati, key=lambda x: x[:2])[2] if candidati else None
    if r is None:
        raise NonTrovato(f"debate not found: {debate_id}")
    return {**r, "title": _titolo(r)}


def get_debate(c: psycopg.Connection, p: DebateId) -> dict:
    punto = _punto(c, p.debate_id)
    data = c.execute("SELECT date FROM sitting WHERE uri = %s", (punto["sitting"],)).fetchone()["date"]
    interventi = c.execute("""SELECT s.person, s.speaker_label, s.as_group, s.as_office, p.given_name, p.family_name
                              FROM speech s LEFT JOIN person p ON p.uri = s.person
                              WHERE s.item = %s AND s.as_office IS DISTINCT FROM 'PRESIDENTE' ORDER BY s.ord""",
                           (punto["uri"],)).fetchall()
    persone = brevi(c, [x["person"] for x in interventi], data)
    governo = _membri_governo(c, [x["person"] for x in interventi if x["person"]], data)
    oratori: dict[str, dict] = {}
    for x in interventi:
        chiave = x["person"] or x["speaker_label"] or "?"
        o = oratori.get(chiave)
        if o is None:
            pb = persone.get(x["person"])
            g = pb.group if pb else None
            ruolo = x["as_office"] if x["as_office"] not in PRESIEDE else None
            al_governo = bool(GOVERNO.match(ruolo or "")) or (not x["as_group"] and x["person"] in governo)
            o = oratori[chiave] = {"name": _titolo_nome(x["given_name"], x["family_name"], x["speaker_label"]),
                                   "party": g.name if g else x["as_group"],
                                   **({"parliamentary_group": "Misto"} if g and g.kind == "misto_component" else {}),
                                   "role": ruolo or (governo.get(x["person"]) if al_governo else None),
                                   "government_member": al_governo, "speech_count": 0}
        o["speech_count"] += 1
    uris_atti = [r["act"] for r in c.execute("SELECT act FROM agenda_item_act WHERE item = %s AND act IS NOT NULL", (punto["uri"],))]
    per_uri = _schede_atti(c, uris_atti)
    schede = list(per_uri.values())
    # le votazioni della seduta sugli atti discussi (legate da vote_act)
    vs = c.execute(SQL_VOTI + """ WHERE v.sitting = %s AND EXISTS (SELECT 1 FROM vote_act x WHERE x.vote = v.uri AND x.act = ANY(%s))
                                  ORDER BY v.number""", (punto["sitting"], uris_atti)).fetchall() if uris_atti else []
    nomi = [f"{o['name']}" + (f" ({o['party']})" if o["party"] else "") for o in oratori.values()]
    # al posto del riassunto scritto da un modello in produzione: titolo e chi interviene, senza modello
    riassunto = (punto["title"] or "").rstrip(".") + "." + (f" Intervengono: {', '.join(nomi)}." if nomi else "")
    return {"next_step": VERIFICA_DOPO, "id": id_vecchio(punto["uri"]), "title": punto["title"],
            "recap": _taglia(riassunto.strip(), 1200), "acts": schede, **_nota_legge(schede),
            "phases": [{"title": punto["title"], "speech_count": len(interventi)}],
            "speakers": list(oratori.values()),
            "votes": [{"id": id_vecchio(v["uri"]), "subject": v["title"], "description": _descrizione(v, per_uri.get(v["atto"])),
                       "outcome": _esito(v), "final_vote": bool(v["final"])} for v in vs]}


# ---------- votazione ----------

def get_vote_details(c: psycopg.Connection, p: VoteDetails) -> dict:
    v = _voto(c, p.vote_id)
    schede = list(_schede_atti(c, [_atto_del_voto(c, v)]).values())
    gruppi = _per_gruppo(c, v)
    out = {"id": id_vecchio(v["uri"]), "subject": v["title"], "description": _descrizione(v, schede[0] if schede else None),
           **({"kind": "quorum_check"} if _numero_legale(v) else {}),
           "outcome": _esito(v), "secret_vote": bool(v["secret"]), "in_favor": v["favor"], "against": v["against"],
           "abstained": v["abstain"], "present": v["present"], "majority": v["majority"], "acts": schede,
           **_nota_legge(schede), "breakdown_by_group": gruppi, "counts_consistency": coerenza(v, gruppi)}
    if not v["secret"]:
        out = {"next_step": f'Call get_vote_hemicycle with vote_id="{out["id"]}" for the per-group numbers of this vote, '
                            "ready to report in words or in a table.", **out}
    singoli = _singoli(c, v)
    if p.deputy or p.group:
        d, g = (p.deputy or "").lower(), (p.group or "").lower()
        singoli = [x for x in singoli if (not d or d in f"{x['first_name'] or ''} {x['last_name'] or ''}".lower())
                   and (not g or g in (x["party"] or "").lower() or g in (x["_sigla"] or "").lower())]
        out["individual_votes"] = singoli
    elif p.include_individual_votes:
        out["individual_votes"] = singoli
    else:
        out["individual_votes_available"] = len(singoli)
    for x in out.get("individual_votes", []):
        x.pop("_sigla", None)
    return out


def get_voted_text(c: psycopg.Connection, p: VoteId) -> dict:
    """Il testo dell'emendamento votato in Aula alla Camera (tabella amendment, sede assembly). Gli articoli e i voti del
    Senato v3 non li lega ancora a un testo: available false, come la produzione fa per i voti senza testo."""
    v = _voto(c, p.vote_id)
    nessuno = {"available": False, "reason": "No extractable text: this vote is not on an amendment/article, or the text was "
                                             "not published."}
    m = re.search(r"\b(?:SUBEM|EM|Emendamento)\.?\s+([\w./-]+)", f"{v['description'] or ''} {v['title'] or ''}", re.I)
    atto = _atto_del_voto(c, v)
    if not m or not atto:
        return nessuno
    e = c.execute("""SELECT text, source_key FROM amendment WHERE act = %s AND number = %s AND venue = 'assembly'
                     ORDER BY sitting_number = %s DESC NULLS LAST, sitting_date DESC NULLS LAST LIMIT 1""",
                  (atto, m.group(1).rstrip("."), int(_URI.match(v["uri"]).group(3)))).fetchone()
    if not e or not e["text"]:
        return nessuno
    k = re.fullmatch(r"leg(\d+)-eme-ac(.+)", e["source_key"] or "")
    fonte = f"https://documenti.camera.it/leg{k.group(1)}/emendamenti/xml/leg.{k.group(1)}.eme.ac.{k.group(2)}.xml" if k else None
    return {"available": True, "paragraphs": [x.strip() for x in e["text"].splitlines() if x.strip()], "source_url": fonte}


def get_vote_hemicycle(c: psycopg.Connection, p: Hemicycle):
    """I numeri dell'emiciclo come in produzione. v3 non disegna il grafico: image_png_url e image_svg_url sono null,
    seat_map è null e nessun blocco immagine accompagna il testo."""
    if p.format not in ("png", "svg"):
        return {"error": f'Unsupported format "{p.format}": use "png" or "svg".'}
    v = _voto(c, p.vote_id)
    totali = {"in_favor": v["favor"], "against": v["against"], "abstained": v["abstain"], "present": v["present"],
              "majority": v["majority"]}
    if v["secret"]:
        return {"available": False, "secret_vote": True,
                "reason": "Secret ballot: individual votes are not public, so there is no hemicycle to draw. Only the aggregate "
                          "totals below are official; the only expressions on record are abstentions.",
                "official_totals": totali, "outcome": _esito(v), "chamber": v["chamber"]}
    if _numero_legale(v):
        return {"available": False, "kind": "quorum_check",
                "reason": "Quorum check (Verifica del numero legale): it counts the senators present and decides nothing, so "
                          "there are no votes to draw.", "present": v["present"], "chamber": v["chamber"]}
    n = c.execute("""SELECT count(*) AS n, count(*) FILTER (WHERE result IN ('favor', 'against')) AS espressi
                     FROM ballot WHERE vote = %s""", (v["uri"],)).fetchone()
    if not n["espressi"]:
        return {"available": False, "secret_vote": False, "reason": "No individual vote data available for this roll call.",
                "official_totals": totali, "outcome": _esito(v), "chamber": v["chamber"]}
    gruppi = _per_gruppo(c, v)
    cc = coerenza(v, gruppi)
    nota = "Grafico non disegnato: questo server restituisce i numeri della votazione per gruppo, senza immagine."
    if cc and cc.get("consistent") is False:
        nota += " Attenzione: la somma dei conteggi per gruppo non coincide con i totali ufficiali del tabellone."
    return {"display": "No chart is drawn for this vote: report the numbers below in words or in a table.",
            "available": True, "vote_id": id_vecchio(v["uri"]), "chamber": v["chamber"], "subject": v["title"],
            "description": _descrizione(v, None), "outcome": _esito(v), "official_totals": totali,
            "breakdown_by_group": gruppi, "counts_consistency": cc, "individual_votes_drawn": n["n"],
            "seat_map": None, "image_png_url": None, "image_svg_url": None, "chart_note": nota}


def get_parliament_agenda(c: psycopg.Connection, p: ParliamentAgenda) -> dict:
    inizio = _data(p.start_date)
    if inizio is None:
        raise NonTrovato("start_date must be YYYY-MM-DD")
    fuori = agenda.agenda(c, inizio, _data(p.end_date) or inizio, _ramo(p.chamber), p.types)
    for giorno in fuori["days"].values():         # gli id che get_session_votes e get_vote_details accettano
        for x in giorno.get("aula", []):
            if x.get("uri"):                          # un giorno del calendario dei lavori non è ancora una seduta
                x["session_id"] = id_vecchio(x["uri"])
        for x in giorno.get("voti", []):
            x["vote_id"] = id_vecchio(x["uri"])
    return fuori


def _atto_da_sigla(c: psycopg.Connection, x: str | None) -> str | None:
    if not x:
        return None
    if x.startswith("it:"):
        return x
    m = re.match(r"\s*(C|S|AC|DDL)\.?\s*(\d+[\w-]*)", x, re.I)
    if not m:
        raise NonTrovato('bill must look like "C. 2750", "S. 1689" or an act uri')
    ramo = "camera" if m.group(1).upper() in ("C", "AC") else "senato"
    return f"it:{ramo}:{LEGISLATURA}:{'ac' if ramo == 'camera' else 'ddl'}:{m.group(2).lower()}"


def search_amendments(c: psycopg.Connection, p: SearchAmendments) -> dict:
    if not (p.text or p.query or p.bill or p.number or p.group):
        raise NonTrovato("give at least one of text, query, bill, number, group")
    return emendamenti.cerca(c, p.text, p.query, _atto_da_sigla(c, p.bill), _ramo(p.chamber), p.group, None, p.outcome, None,
                             _data(p.start_date), _data(p.end_date), p.max_results, 0, p.number)


def get_amendment(c: psycopg.Connection, p: AmendmentId) -> dict:
    out = emendamenti.scheda(c, p.amendment_id)
    if out is None:
        raise NonTrovato("amendment not found")
    return out


# ---------- registro ----------

def _d(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


STRUMENTI: list[Strumento] = [
    Strumento("search_parliament", _d("""Search Italian parliamentary records: floor and committee speeches and parliamentary
        acts (bills, motions, written questions) of the Chamber of Deputies and the Senate, 19th legislature (Oct 2022 -
        today). Each result says its `chamber`. Keyword search in Italian (plurals fold; "quoted phrase", -word, or):
        Italian queries work best ("salario minimo", "intelligenza artificiale", company names, people). `is_exact` says
        whether the phrase occurs verbatim. Acts are matched on their title. Every speech of the Chamber has `url`, its
        page in the official record; a Senate speech has the page of its sitting when known. For a speaker of the Mixed Group, `group` is the component they belonged to that day:
        attribute the position to the component, never to the Mixed Group as a whole."""), SearchParliament, search_parliament),
    Strumento("list_sessions", _d("""List plenary sittings of the Chamber of Deputies and the Senate (each says its
        `chamber`), most recent first, each with a one-line recap built from its agenda (Italian), its debates and counts
        of speeches/votes."""), ListSessions, list_sessions),
    Strumento("get_session_votes", _d("""List every roll-call vote of one sitting: subject, description, kind (final vote
        flag), outcome and aggregate counts. A Senate vote's `description` names the bill it was on. `kind` "quorum_check"
        marks a Senate check of the quorum (Verifica del numero legale): it counts who is present and decides nothing, so
        it has no outcome; never report it as a rejected vote."""), SessionId, get_session_votes),
    Strumento("get_vote_details", _d("""Full detail of one roll-call vote: aggregates, per-group breakdown (the Mixed Group
        by component), linked act (with official page and full-text PDF), secret-ballot flag, and optionally the
        individual votes (~400 deputies or ~200 senators). A linked act that became law carries `law`. In secret ballots
        individual expressions are not public: the "secret_vote" flag tells you when that is the case."""),
        VoteDetails, get_vote_details),
    Strumento("get_voted_text", _d("""Exact full text of the amendment a Chamber roll call voted on, from the official
        amendment file. Returns a clear message for other votes (final votes, articles, agenda items, procedural votes,
        Senate votes)."""), VoteId, get_voted_text),
    Strumento("get_debate", _d("""Detail of one debate: a recap built from its title and speakers, discussed acts (with
        `law` when an act became law), the speakers with their party (for the Mixed Group, the component they belonged to
        on that day) and speech counts, and the roll calls on the discussed acts (get_session_votes lists every vote of the
        sitting)."""), DebateId, get_debate),
    Strumento("get_vote_hemicycle", _d("""The numbers behind the hemicycle of a roll-call vote: official totals, per-group
        breakdown and a counts-consistency check. This server draws no chart: image_png_url and image_svg_url are null,
        report the numbers in words or in a table. For secret ballots it returns the aggregate totals with an explanation."""),
        Hemicycle, get_vote_hemicycle),
    Strumento("get_parliament_agenda", _d("""What happens in Parliament day by day between two dates: plenary sittings
        (planned ones from the Chamber's order of business, and held ones), committee sittings, amendment deadlines in
        committee, bills filed, final votes and laws published. Amendment deadlines come from the committees' summary
        records, read by fixed rules and confirmed by a second reading: each carries the sentence of the record (written by
        the clerks, not words of a member of Parliament), its date and time, and `superseded` when a later sitting moved it.
        For "what expires today / this week" ask types ["termini"]."""), ParliamentAgenda, get_parliament_agenda),
    Strumento("search_amendments", _d("""Search amendments of the Chamber of Deputies and the Senate, 19th legislature, across all
        bills or in one: by meaning (`text`: a topic, a sentence, or the text of a draft amendment, to find similar ones
        already tabled), by words, by number, group, outcome or dates. Each result has its signatories with their group that
        day, and an outcome (`esito`) from a fixed list with its source (`fonte`): the Chamber or Senate file, the Chamber's
        electronic floor vote, or the confidence-vote rule (amendments fall when the government puts a confidence vote on the
        article). "non_pubblicato" means no source states the outcome: never report it as rejected."""), SearchAmendments, search_amendments),
    Strumento("get_amendment", _d("""One amendment in full: text, signatories and groups, outcome with its source, the vote
        of each group on the floor when there was a roll-call vote, its history (the same or almost the same text tabled in
        other bills, with each outcome), the speeches of the voting sitting that cite it (excerpts of the official record:
        quote them only word for word), the opinions of government and rapporteur read in the committee summaries, and the
        bill's amendment deadlines. Data in Italian."""), AmendmentId, get_amendment),
]
PER_NOME = {s.nome: s for s in STRUMENTI}
TITOLI = {"search_parliament": "Search parliamentary records",
          "list_sessions": "List plenary sittings", "get_session_votes": "List roll-call votes of a sitting",
          "get_vote_details": "Get roll-call vote details", "get_voted_text": "Get the voted amendment/article text",
          "get_debate": "Get debate details", "get_vote_hemicycle": "Vote hemicycle: numbers",
          "get_parliament_agenda": "Parliament agenda: sittings, deadlines, bills, votes",
          "search_amendments": "Search amendments, with outcome and source", "get_amendment": "Amendment in full: history, debate, opinions"}


def esegui(c: psycopg.Connection, nome: str, argomenti: dict) -> object:
    """Esegue uno strumento pubblico con argomenti non fidati: li valida prima (ValidationError se non vanno)."""
    s = PER_NOME[nome]
    return s.esegui(c, s.parametri.model_validate(argomenti))
