"""Emendamenti: un modulo per chat, MCP e sito (card 284). Tre cose:

- `esito`: l'esito di un emendamento in un elenco fisso, sempre con la fonte da cui viene. La fonte può essere il file
  della Camera o del Senato, il voto elettronico dell'Aula della Camera (che il file non riporta), oppure la regola della
  fiducia: in Aula, quando il governo pone la fiducia su un articolo «senza emendamenti», gli emendamenti non votati di
  quell'articolo decadono. Quando nessuna fonte lo dice, l'esito è «non pubblicato»: mai un «respinto» dedotto.
- `cerca`: gli emendamenti di tutta la legislatura, per significato (anche il testo di una bozza), per parole o per
  filtri: atto, ramo, gruppo, firmatario, esito, periodo.
- `scheda`: un emendamento con testo, firmatari, esito, storia (lo stesso testo o quasi in altri atti), voto dei
  gruppi, interventi della seduta che lo citano, pareri di governo e relatore letti nei sommari, termini dell'atto."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from collections import defaultdict

import psycopg

# ---------- esiti ----------

# (espressione sull'esito della fonte, codice, etichetta): il primo che corrisponde vince
ESITI = [
    (r"riformulat", "approvato_riformulato", "Approvato riformulato"),
    (r"^approvat|^accolt[oa]$|^accolto\b(?!.*raccomandazione)", "approvato", "Approvato"),
    (r"come raccomandazione", "accolto_raccomandazione", "Accolto come raccomandazione"),
    (r"^non accolt", "non_accolto", "Non accolto"),
    (r"trasformat.*ordin|trasformat.*odg|ordine del giorno", "ritirato_odg", "Ritirato e trasformato in ordine del giorno"),
    (r"^ritirat", "ritirato", "Ritirato"),
    (r"^respint", "respinto", "Respinto"),
    (r"inammissibil", "inammissibile", "Inammissibile"),
    (r"improponibil", "improponibile", "Improponibile"),
    (r"irricevibil", "irricevibile", "Irricevibile"),
    (r"improcedibil", "improcedibile", "Improcedibile"),
    (r"^preclus|preclusa la restante", "precluso", "Precluso"),
    (r"^assorbit", "assorbito", "Assorbito"),
    (r"^decadut", "decaduto", "Decaduto"),
    (r"^accantonat", "accantonato", "Accantonato"),
    (r"non posto in votazione", "non_votato", "Non posto in votazione"),
    (r"^v\.\s*testo|^vedi testo|^sost\. id|^id\. em", "altro_testo", "Esito sul testo collegato"),
    (r"^riammess", "riammesso", "Riammesso"),
]
ETICHETTE = {c: t for _, c, t in ESITI} | {"decaduto_fiducia": "Decaduto per la fiducia", "non_pubblicato": "Esito non pubblicato",
                                         "altro": "Altro esito"}
CODICI = sorted(ETICHETTE)


def esito_fonte(raw: str | None) -> str | None:
    """L'esito scritto dalla fonte, nell'elenco fisso; None se la fonte non lo scrive."""
    if not raw or not raw.strip():
        return None
    low = raw.strip().lower()
    return next((c for r, c, _ in ESITI if re.search(r, low)), "altro")


def _numero_atto(act: str) -> str:
    return act.rsplit(":", 1)[-1]


def _fiducie(c: psycopg.Connection, atti: list[str]) -> dict[str, list[dict]]:
    """Le fiducie poste alla Camera sugli atti, con l'articolo su cui sono poste («Articolo 1, sulla cui approvazione,
    senza emendamenti…»; «articolo unico»)."""
    out: dict[str, list[dict]] = defaultdict(list)
    for r in c.execute("""SELECT va.act, v.uri, v.date, v.description FROM vote v JOIN vote_act va ON va.vote = v.uri
                          WHERE v.confidence AND v.chamber = 'camera' AND va.act = ANY(%s)""", (atti,)):
        d = r["description"] or ""
        m = re.search(r"\barticol[oi]\s+(\d+[\w-]*)", d, re.I)
        out[r["act"]].append({"voto": r["uri"], "data": r["date"], "articolo": None if re.search(r"articolo unico", d, re.I) else (m.group(1) if m else None),
                              "testo": d[:300]})
    return out


class Esiti:
    """Calcola gli esiti di un gruppo di emendamenti, leggendo voti e fiducie una volta per atto."""

    def __init__(self, c: psycopg.Connection):
        self.c, self._voti, self._fid = c, {}, {}

    def _voti_aula(self, act: str) -> dict[str, dict]:
        if act not in self._voti:
            from ..sito_emendamenti import _voti_aula
            self._voti[act] = _voti_aula(self.c, _numero_atto(act)) if act.startswith("it:camera:") else {}
        return self._voti[act]

    def prepara(self, atti: list[str]) -> None:
        nuovi = [a for a in set(atti) if a not in self._fid]
        if nuovi:
            f = _fiducie(self.c, nuovi)
            self._fid.update({a: f.get(a, []) for a in nuovi})

    def di(self, r: dict) -> dict:
        """r: una riga di amendment (uri, act, number, venue, article, outcome)."""
        codice = esito_fonte(r["outcome"])
        if codice:
            return {"esito": codice, "etichetta": ETICHETTE[codice], "fonte": "file della " + ("Camera" if r["uri"].startswith("it:camera:") else "Senato"),
                    "come_scritto": r["outcome"]}
        if r["uri"].startswith("it:camera:") and r["venue"] == "assembly":
            v = self._voti_aula(r["act"]).get(r["number"])
            if v:
                return {"esito": v["outcome"], "etichetta": ETICHETTE[v["outcome"]], "fonte": "voto elettronico dell'Aula",
                        "voto": v["id"], "url": v["url"], "favorevoli": v["in_favor"], "contrari": v["against"], "astenuti": v["abstained"]}
            self.prepara([r["act"]])
            for f in self._fid.get(r["act"], []):
                if f["articolo"] is None or (r["article"] or "").split("-")[0] == f["articolo"].split("-")[0]:
                    return {"esito": "decaduto_fiducia", "etichetta": ETICHETTE["decaduto_fiducia"], "fonte": "regola della fiducia",
                            "voto": f["voto"], "nota": f"fiducia del {f['data'].isoformat()}: «{f['testo'][:160]}»"}
        return {"esito": "non_pubblicato", "etichetta": ETICHETTE["non_pubblicato"], "fonte": None,
                "nota": "né il file della fonte né i voti dicono com'è finito"}


# ---------- firmatari, atti ----------

SQL_FIRME = """
SELECT s.amendment, s.ord, s.first, s.person, s.kind_raw,
       nullif(trim(concat_ws(' ', p.given_name, p.family_name)), '') AS nome,
       nullif(trim(concat_ws(' ', s.given_raw, s.family_raw)), '') AS grezzo,
       g.name AS gruppo, g.kind AS tipo_gruppo, gp.name AS gruppo_padre
FROM amendment e JOIN amendment_signer s ON s.amendment = e.uri
LEFT JOIN person p ON p.uri = s.person
LEFT JOIN grp g ON g.uri = group_at(s.person, coalesce(e.presented, e.sitting_date, current_date))
LEFT JOIN grp gp ON gp.uri = g.part_of
WHERE e.uri = ANY(%s) ORDER BY s.amendment, s.ord"""


def _firme(c: psycopg.Connection, uris: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for f in c.execute(SQL_FIRME, (uris,)):
        gruppo = f"{f['gruppo']} ({f['gruppo_padre']})" if f["tipo_gruppo"] == "misto_component" and f["gruppo_padre"] else f["gruppo"]
        out[f["amendment"]].append({"nome": f["nome"] or (f["grezzo"] or "").title() or (f["kind_raw"] or "").capitalize() or "non indicato",
                                    "persona": f["person"], "gruppo": gruppo or ((f["kind_raw"] or "").capitalize() or None),
                                    "primo": bool(f["first"])})
    return out


def _atti(c: psycopg.Connection, uris: list[str]) -> dict[str, dict]:
    return {r["uri"]: r for r in c.execute("SELECT uri, chamber, number, title, card_url FROM act WHERE uri = ANY(%s)", (list(set(uris)),))}


def _sigla_atto(a: dict | None, uri: str) -> str:
    n = (a or {}).get("number") or _numero_atto(uri)
    return f"{'C.' if uri.startswith('it:camera:') else 'S.'} {n}"


def impronta(testo: str | None) -> str:
    """Il testo senza maiuscole, punteggiatura e spazi: due emendamenti con la stessa impronta dicono la stessa cosa."""
    return hashlib.md5(re.sub(r"[^a-z0-9àèéìòù]+", "", (testo or "").lower()).encode()).hexdigest()


def _riga(r: dict, atto: dict | None, firme: list[dict], esito: dict, testo_max: int = 400) -> dict:
    t = r["text"] or ""
    return {"uri": r["uri"], "numero": r["number"], "atto": r["act"], "sigla_atto": _sigla_atto(atto, r["act"]),
            "titolo_atto": ((atto or {}).get("title") or "")[:200], "link_atto": (atto or {}).get("card_url"),
            "ramo": r["uri"].split(":")[1], "sede": "Aula" if r["venue"] == "assembly" else "commissione",
            "articolo": r["article"], "data": (r.get("d") or r.get("presented") or r.get("sitting_date")),
            "testo": t[:testo_max] + ("…" if len(t) > testo_max else ""), "firmatari": firme,
            "gruppi": sorted({f["gruppo"] for f in firme if f["gruppo"]}), **esito}


# ---------- ricerca ----------

COLONNE = "e.uri, e.act, e.number, e.venue, e.article, e.outcome, e.text, coalesce(e.presented, e.sitting_date) AS d"


def cerca(c: psycopg.Connection, testo: str | None = None, q: str | None = None, act: str | None = None, chamber: str | None = None,
          group: str | None = None, signer: str | None = None, outcome: str | None = None, venue: str | None = None,
          start: dt.date | None = None, end: dt.date | None = None, limit: int = 20, offset: int = 0, number: str | None = None) -> dict:
    """Emendamenti di tutta la legislatura. Con `testo` per significato (un tema, una frase, il testo di una bozza),
    dal più vicino; senza, per filtri e parole (`q`), dal più recente. L'esito è sempre calcolato e filtrabile."""
    dove, p = ["true"], {"lim": limit, "off": offset}
    if act:
        dove.append("e.act = %(atto)s"); p["atto"] = act
    if number:
        dove.append("rtrim(e.number, '.') = %(num)s"); p["num"] = number.strip().rstrip(".")
    if chamber:
        dove.append("split_part(e.uri, ':', 2) = %(ramo)s"); p["ramo"] = chamber
    if venue:
        dove.append("(e.venue = 'assembly') = %(aula)s"); p["aula"] = venue == "assembly"
    if start:
        dove.append("coalesce(e.presented, e.sitting_date) >= %(da)s"); p["da"] = start
    if end:
        dove.append("coalesce(e.presented, e.sitting_date) <= %(a)s"); p["a"] = end
    if q:
        dove.append("to_tsvector('italian', coalesce(e.text, '')) @@ websearch_to_tsquery('italian', %(q)s)"); p["q"] = q
    if signer:
        from .comune import stessa_persona
        dove.append("EXISTS (SELECT 1 FROM amendment_signer s WHERE s.amendment = e.uri AND s.person = ANY(%(firm)s))"); p["firm"] = stessa_persona(c, signer)
    if group:
        dove.append("""EXISTS (SELECT 1 FROM amendment_signer s JOIN grp g ON g.uri = group_at(s.person, coalesce(e.presented, e.sitting_date, current_date))
                       WHERE s.amendment = e.uri AND (%(gruppo)s IN (g.uri, g.short_name, g.part_of) OR g.name ILIKE %(gruppo_l)s))""")
        p["gruppo"], p["gruppo_l"] = group, f"%{group}%"
    sim: dict[str, float] = {}
    if testo:
        from ..fascicolo import modello
        from ..fascicolo.recupero_canali import vicini
        from .significato import SOGLIA
        vettore = modello.letterale(modello.vettori([testo[:6000]])[0])
        brani = [b for b in vicini(c, vettore, ["amendment"], 400, rami=[chamber] if chamber else None) if b["similarita"] >= SOGLIA]
        for b in brani:
            sim[b["uri"]] = max(sim.get(b["uri"], 0), b["similarita"])
        dove.append("e.uri = ANY(%(vicini)s)"); p["vicini"] = list(sim)
    righe = c.execute(f"SELECT {COLONNE} FROM amendment e WHERE {' AND '.join(dove)} "
                      + ("" if testo else "ORDER BY coalesce(e.presented, e.sitting_date) DESC NULLS LAST, e.uri ")
                      + ("LIMIT 2000" if testo or outcome else "LIMIT %(lim)s OFFSET %(off)s"), p).fetchall()
    totale = len(righe) if testo or outcome else c.execute(f"SELECT count(*) AS n FROM amendment e WHERE {' AND '.join(dove)}", p).fetchone()["n"]
    es = Esiti(c)
    es.prepara([r["act"] for r in righe])
    calcolati = [(r, es.di(r)) for r in righe]
    if outcome:
        calcolati = [(r, x) for r, x in calcolati if x["esito"] == outcome]
        totale = len(calcolati)
    if testo:
        calcolati.sort(key=lambda rx: -sim.get(rx[0]["uri"], 0))
    if testo or outcome:
        calcolati = calcolati[offset:offset + limit]
    uris = [r["uri"] for r, _ in calcolati]
    firme, atti = _firme(c, uris), _atti(c, [r["act"] for r, _ in calcolati])
    items = []
    for r, x in calcolati:
        it = _riga(r, atti.get(r["act"]), firme.get(r["uri"], []), x)
        if testo:
            it["similarita"] = round(sim[r["uri"]], 3)
        items.append(it)
    return {"total": totale, "items": items,
            "nota": ("per significato: controlla che parlino davvero del tema. " if testo else "")
                    + "L'esito viene dalla fonte indicata in «fonte»; «non pubblicato» vuol dire che nessuna fonte lo dice, non che è stato respinto."}


# ---------- scheda ----------

def _storia(c: psycopg.Connection, r: dict) -> list[dict]:
    """Lo stesso testo (o quasi) presentato in altri atti o in altre sedi: i vicini per significato, tenuti se il testo
    coincide (stessa impronta) o è quasi uguale (similarità alta)."""
    from ..fascicolo.recupero_canali import vicini
    v = c.execute("""SELECT pv.embedding::text AS e FROM passage p JOIN passage_vector pv ON pv.hash = p.hash
                     WHERE p.source = 'amendment' AND p.uri = %s ORDER BY p.ord LIMIT 1""", (r["uri"],)).fetchone()
    if not v:
        return []
    brani = [b for b in vicini(c, v["e"], ["amendment"], 60) if b["uri"] != r["uri"] and b["similarita"] >= 0.93]
    if not brani:
        return []
    sim = {}
    for b in brani:
        sim[b["uri"]] = max(sim.get(b["uri"], 0), b["similarita"])
    righe = c.execute(f"SELECT {COLONNE} FROM amendment e WHERE e.uri = ANY(%s)", (list(sim),)).fetchall()
    mia = impronta(r["text"])
    es = Esiti(c); es.prepara([x["act"] for x in righe])
    firme, atti = _firme(c, [x["uri"] for x in righe]), _atti(c, [x["act"] for x in righe])
    out = []
    for x in righe:
        uguale = impronta(x["text"]) == mia
        if not uguale and sim[x["uri"]] < 0.96:
            continue
        it = _riga(x, atti.get(x["act"]), firme.get(x["uri"], []), es.di(x), testo_max=200)
        it["uguale"] = uguale
        it["similarita"] = round(sim[x["uri"]], 3)
        out.append(it)
    out.sort(key=lambda x: str(x["data"] or ""))
    return out[:20]


def _dibattito(c: psycopg.Connection, r: dict, voto: str | None) -> list[dict]:
    """Gli interventi della seduta in cui l'emendamento è stato votato che lo citano per numero."""
    if not voto:
        return []
    sed = c.execute("SELECT sitting FROM vote WHERE uri = %s", (voto,)).fetchone()
    if not sed:
        return []
    # «emendamento 1.1», «l'articolo aggiuntivo 7.01», «subemendamento 0.1.1.2»: il numero dopo la parola, non dentro un
    # codice (M2C3I1.1) o un ordine del giorno (9/2750/11)
    cita = rf"(emendament\w*|articol\w* aggiuntiv\w*)\s+(?:n\.\s*|tab\.\s*)?(?:[\w.]+,\s*)*{re.escape(r['number'])}(?![\d])"
    righe = c.execute("""SELECT s.uri, s.text, s.person, s.as_group, nullif(trim(concat_ws(' ', p.given_name, p.family_name)), '') AS nome,
                                st.date, st.number AS seduta
                         FROM speech s JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
                         LEFT JOIN person p ON p.uri = s.person
                         WHERE i.sitting = %s AND s.kind IS DISTINCT FROM 'summary' AND s.text ~* %s
                         ORDER BY i.ord, s.ord LIMIT 12""", (sed["sitting"], cita)).fetchall()
    out = []
    for x in righe:
        m = re.search(cita, x["text"], re.I)
        a, b = max(0, m.start() - 350), min(len(x["text"]), m.end() + 350)
        out.append({"intervento": x["uri"], "chi": x["nome"], "persona": x["person"], "gruppo_nel_resoconto": x["as_group"],
                    "data": x["date"], "seduta": x["seduta"], "estratto": ("…" if a else "") + x["text"][a:b] + ("…" if b < len(x["text"]) else ""),
                    "url": _url_intervento(x["uri"], x["seduta"])})
    return out


def _url_intervento(uri: str, seduta: int | None) -> str | None:
    m = re.match(r"it:camera:19:sed(\d+):(tit[\w.]+)$", uri)
    if m:
        n = int(m.group(1))
        return f"https://www.camera.it/leg19/410?idSeduta={n:04d}&tipo=stenografico#sed{n:04d}.stenografico.{m.group(2)}"
    return None


def scheda(c: psycopg.Connection, uri: str) -> dict | None:
    r = c.execute(f"SELECT {COLONNE}, e.kind FROM amendment e WHERE e.uri = %s", (uri,)).fetchone()
    if not r:
        return None
    es = Esiti(c)
    x = es.di(r)
    atto = _atti(c, [r["act"]]).get(r["act"])
    out = _riga(r, atto, _firme(c, [uri]).get(uri, []), x, testo_max=20000)
    out["tipo"] = r["kind"]
    if x.get("voto") and x["fonte"] == "voto elettronico dell'Aula":
        from ..sito_emendamenti import _per_gruppo
        out["voto_gruppi"] = _per_gruppo(c, x["voto"])
    out["storia"] = _storia(c, r)
    out["dibattito"] = _dibattito(c, r, x.get("voto"))
    out["pareri"] = [{"chi": f["subject"], "parere": f["outcome"], "data": f["sitting_date"], "organo": f["body_name"], "frase": f["evidence"]}
                     for f in c.execute("""SELECT subject, outcome, sitting_date, body_name, evidence FROM committee_fact
                                           WHERE kind = 'amendment_opinion' AND act = %s AND %s = ANY(amendments)
                                           ORDER BY sitting_date""", (r["act"], r["number"]))]
    out["termini_atto"] = [{"tipo": t["kind"], "evento": t["event"], "scadenza": t["due_date"], "ora": t["due_time"], "organo": t["body_name"], "frase": t["sentence"]}
                           for t in c.execute("""SELECT kind, event, due_date, due_time, body_name, sentence FROM amendment_deadline
                                                 WHERE act = %s ORDER BY due_date""", (r["act"],))]
    out["avvertenze"] = ("I pareri sono letti nei sommari delle commissioni (ultimi mesi) e possono mancare. Gli estratti del dibattito "
                   "sono del resoconto: si citano tra «…» solo copiati parola per parola.")
    return out

