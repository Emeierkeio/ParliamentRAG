"""Autorevolezza di chi parla su un tema: Σ peso × componente, ogni componente in [0, 1] e relativa agli altri
parlamentari per la stessa domanda. Stessa formula, stessi pesi e parametri del backend precedente.

Sei componenti:
- interventi: la quota dei brani d'Aula più vicini alla domanda (2.000), col decadimento nel tempo;
- atti: la quota degli atti più vicini (500 per testo degli atti di sindacato e indirizzo, 500 per titolo dei progetti
  di legge), primo firmatario 1, cofirmatario 0,3, col decadimento;
- commissione: la commissione più pertinente in cui siede alla data (parole chiave in commissioni_temi.json, se no il
  nome dell'organo), dalla mediana (0) alla migliore (1);
- professione e istruzione: il brano della scheda contro la domanda, dalla mediana (0) al 95° percentile (1);
- ruolo: incarico di governo o carica in un organo (con un bonus se l'organo è pertinente), altrimenti 0,3.

Due tipi di dati. I profili (gruppi, sedi, cariche, schede) non dipendono dalla domanda: si leggono una volta e restano
in memoria per sei ore. Le evidenze sul tema vengono da tre ricerche dei vicini per domanda (pgvector, `<=>`), che
restituiscono id e punteggi, mai vettori. Chi passa da maggioranza a opposizione (o il contrario) perde quello che ha
fatto prima: l'autorevolezza non passa da uno schieramento all'altro. Lo schieramento di un gruppo (o di una componente
del Misto) alla data è la regola unica di maggioranza.py: voti di fiducia dei dodici mesi prima, riserva i membri al
governo.

Senza l'indice HNSW su passage_vector la ricerca dei vicini legge tutti i vettori (15-30 secondi): per quelle query il
tempo massimo sale a 30 secondi."""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
import re
import threading
import time
import unicodedata
from collections import OrderedDict
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from ..strumenti.comune import LEGISLATURA, RAMI
from . import maggioranza, modello
from .maggioranza import MAGGIORANZA, MISTO, OPPOSIZIONE, lato_alla_data  # noqa: F401 (lato_alla_data: per i test)

log = logging.getLogger("parliamentrag.fascicolo.autorevolezza")

COMPONENTI = ("profession", "education", "committee", "acts", "interventions", "role")
PESI = {"profession": 0.15, "education": 0.10, "committee": 0.25, "acts": 0.20, "interventions": 0.25, "role": 0.05}
EMIVITA_ATTI = EMIVITA_INTERVENTI = 548          # giorni: 18 mesi
TETTO = 0.8                                      # ogni componente si taglia qui prima del peso
K_BRANI, K_ATTI = 2000, 500                      # quanti vicini definiscono «sul tema»
SENZA_DATA = 0.5                                 # decadimento di un atto senza data (circa 18 mesi)
PRIMO, COFIRMATARIO = 1.0, 0.3
DURATA_PROFILI = 6 * 3600
TEMPO_MASSIMO = "30s"                            # per le ricerche dei vicini, finché l'indice HNSW non c'è

# cariche negli organi (office.title con target un organo) e incarichi di governo (office.title con target il governo
# o un ministero): pesi del backend precedente
CARICHE_ORGANO = {"chair": (0.7, "Presidente"), "vice_chair": (0.5, "Vicepresidente"), "secretary": (0.4, "Segretario"),
                  "group_whip": (0.4, "Capogruppo")}
CARICHE_GOVERNO = {"prime_minister": 1.0, "deputy_prime_minister": 0.95, "minister": 0.9, "minister_without_portfolio": 0.9,
                   "vice_minister": 0.8, "undersecretary": 0.7}
RUOLO_BASE, BONUS_PERTINENZA = 0.3, 0.3

# organi il cui nome dice di cosa si occupano; quelli procedurali (giunte, uffici di presidenza, delegazioni) stanno
# vicino a qualunque domanda per caso e farebbero «esperti» di tutto i loro membri
ORGANO_TEMATICO = re.compile(r"INCHIESTA|^COMITATO PERMANENTE|^COMMISSIONE PARLAMENTARE|^COMITATO PARLAMENTARE"
                             r"|^\d+A COMMISSIONE PERMANENTE")
TEMI_COMMISSIONI: dict[str, list[str]] = json.loads((Path(__file__).with_name("commissioni_temi.json")).read_text("utf-8"))

GOVERNO = "GOVERNO"


# ---------- funzioni pure ----------

def chiave_nome(nome: str | None) -> str:
    """Chiave senza accenti, apostrofi e spazi doppi: «ATTIVITA'» e «ATTIVITÀ» sono lo stesso organo."""
    t = unicodedata.normalize("NFKD", nome or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).replace("'", "").replace("’", "")
    return " ".join(t.upper().split())


_TEMI = {chiave_nome(n): kw for n, kw in TEMI_COMMISSIONI.items() if kw}
_TEMI_BREVI = {k.split(" (", 1)[0]: n for n, k in ((n, chiave_nome(n)) for n in TEMI_COMMISSIONI) if " (" in k}


def temi_organo(nome: str) -> tuple[str | None, list[str]]:
    """Il nome completo e le parole chiave di un organo, se ci sono: le commissioni permanenti della Camera si chiamano
    «XI Commissione» e prendono il nome lungo da commissioni_temi.json."""
    k = chiave_nome(nome)
    if k in _TEMI:
        return None, _TEMI[k]
    lungo = _TEMI_BREVI.get(k)
    if lungo:
        return lungo, TEMI_COMMISSIONI[lungo]
    for chiave, kw in _TEMI.items():                     # il Senato aggiunge il nome breve tra parentesi
        if k.startswith(chiave):
            return None, kw
    return None, []


def tematico(nome: str) -> bool:
    return bool(temi_organo(nome)[1]) or bool(ORGANO_TEMATICO.search(chiave_nome(nome)))


def attivo(inizio: dt.date | None, fine: dt.date | None, il: dt.date) -> bool:
    """Vero se [inizio, fine] copre `il`; un estremo che manca è aperto."""
    return (inizio is None or inizio <= il) and (fine is None or fine >= il)


def decadimento(giorni: int, emivita: int) -> float:
    return 1.0 if giorni < 0 else math.exp(-math.log(2) / emivita * giorni)


def pesi_tema(righe: Iterable[dict], riferimento: dt.date, emivita: int, valida: Callable[[str, dt.date | None], bool],
              senza_data: float, peso_ruolo: Callable[[dict], float] = lambda r: 1.0) -> dict[str, float]:
    """Per persona, Σ decadimento × vicinanza sugli elementi più vicini alla domanda. Le righe vengono da una ricerca dei
    vicini: esserci vuol già dire «sul tema». La vicinanza riporta il punteggio a [0,5, 1] dentro i risultati, così il
    più vicino conta il doppio dell'ultimo entrato. Più righe della stessa coppia (persona, elemento), i brani di un
    intervento, contano una volta."""
    migliori: dict[tuple[str, str], dict] = {}
    for r in righe:
        k = (r["sid"], r["item"])
        if k not in migliori or r["score"] > migliori[k]["score"]:
            migliori[k] = r
    if not migliori:
        return {}
    punti = [r["score"] for r in migliori.values()]
    basso, ampiezza = min(punti), max(punti) - min(punti)
    pesi: dict[str, float] = {}
    for r in migliori.values():
        quando = r.get("date")
        if quando is not None and quando > riferimento:
            continue
        if not valida(r["sid"], quando):
            continue
        d = decadimento((riferimento - quando).days, emivita) if quando is not None else senza_data
        vicinanza = 0.5 + 0.5 * ((r["score"] - basso) / ampiezza if ampiezza > 0 else 1.0)
        pesi[r["sid"]] = pesi.get(r["sid"], 0.0) + peso_ruolo(r) * d * vicinanza
    return pesi


def relativo_log(pesi: dict[str, float]) -> dict[str, float]:
    """log(1+w) / log(1+w_max): il più attivo sul tema prende 1."""
    massimo = max(pesi.values(), default=0.0)
    if massimo <= 0:
        return {}
    return {k: math.log1p(w) / math.log1p(massimo) for k, w in pesi.items() if w > 0}


def percentile(valori: list[float], p: float) -> float:
    """Il percentile con l'interpolazione lineare (lo stesso metodo predefinito di numpy)."""
    v = sorted(valori)
    if not v:
        return 0.0
    x = (len(v) - 1) * p / 100
    i = math.floor(x)
    return v[i] if i + 1 >= len(v) else v[i] + (v[i + 1] - v[i]) * (x - i)


def relativo_simile(simili: dict[str, float], basso_pct: float = 50, alto_pct: float = 95) -> dict[str, float]:
    """Coseni grezzi in [0, 1] contro la popolazione della domanda: sotto la mediana 0, dal 95° percentile in su 1. I
    coseni stanno in una fascia stretta: con (cos+1)/2 la componente misurerebbe se il dato c'è, non se è pertinente."""
    if not simili:
        return {}
    valori = list(simili.values())
    basso, alto = percentile(valori, basso_pct), percentile(valori, alto_pct)
    if alto <= basso:
        return {k: 1.0 if v >= alto else 0.0 for k, v in simili.items()}
    return {k: min(1.0, max(0.0, (v - basso) / (alto - basso))) for k, v in simili.items()}


def punteggio_ruolo(governo: list[dict], cariche: list[dict], pertinenza: dict[str, float],
                    riferimento: dt.date) -> tuple[float, str | None]:
    """Il migliore fra incarico di governo, carica in un organo (col bonus di pertinenza) e la base 0,3."""
    migliore, etichetta = RUOLO_BASE, None
    for g in governo:
        peso = CARICHE_GOVERNO.get(g["title"], 0.0)
        if attivo(g["start"], g["end"], riferimento) and peso > migliore:
            migliore, etichetta = peso, g["label"]
    for k in cariche:
        if k["title"] not in CARICHE_ORGANO or not attivo(k["start"], k["end"], riferimento):
            continue
        base, nome = CARICHE_ORGANO[k["title"]]
        peso = base * (1 + BONUS_PERTINENZA * pertinenza.get(k["body"], 0.0))
        if peso > migliore:
            migliore, etichetta = peso, f"{nome} {k['body_name']}".strip()
    return migliore, etichetta


def punteggio_commissione(sedi: list[dict], pertinenza: dict[str, float], riferimento: dt.date) -> float:
    """La pertinenza dell'organo più vicino al tema fra quelli in cui siede alla data."""
    return max((pertinenza.get(s["body"], 0.0) for s in sedi if attivo(s["start"], s["end"], riferimento)), default=0.0)


def pesi_richiesta(scelti: dict | None, modello_pesi: dict[str, float] = PESI) -> dict[str, float] | None:
    """I pesi scelti da chi chiede, riportati al totale del modello perché i punteggi restino sulla stessa scala; None se
    non si possono usare (componenti negative o non numeriche, niente sopra zero) e valgono quelli del modello."""
    if not scelti:
        return None
    presi = {}
    for k in COMPONENTI:
        try:
            v = float(scelti.get(k, 0.0))
        except (TypeError, ValueError):
            return None
        if v != v or v < 0:
            return None
        presi[k] = v
    totale = sum(presi.values())
    if totale <= 0:
        return None
    scala = (sum(modello_pesi.values()) or 1.0) / totale
    return {k: v * scala for k, v in presi.items()}


def pesi_persona(senza_istruzione: bool, pesi: dict[str, float]) -> dict[str, float]:
    """Se la fonte non pubblica l'istruzione (il Senato), il suo peso va alle altre componenti in proporzione: un dato
    che manca alla fonte non conta come zero."""
    if not senza_istruzione or not pesi.get("education"):
        return pesi
    resto = {k: w for k, w in pesi.items() if k != "education"}
    scala = sum(pesi.values()) / (sum(resto.values()) or 1.0)
    return {**{k: w * scala for k, w in resto.items()}, "education": 0.0}


def compatibili(prima: str, dopo: str) -> bool:
    """Falso solo fra maggioranza e opposizione: il Misto ha componenti di tutti e due i lati."""
    return {prima, dopo} != {MAGGIORANZA, OPPOSIZIONE}


def valida(gruppi: list[dict], lato: Callable[..., str], attuale: str | None, quando: dt.date | None,
           oggi: dt.date | None = None) -> bool:
    """Se un'attività del giorno `quando` conta ancora per lo schieramento di oggi: il lato del gruppo di allora, a quella
    data, contro il lato del gruppo di oggi. Chi non ha gruppi (membri del governo da fuori) tiene tutto; un'attività
    senza data conta se la persona non ha mai cambiato schieramento."""
    if not gruppi:
        return True
    adesso = lato(attuale, oggi)
    if quando is None:
        return all(compatibili(lato(g["grp"], g["end"] or oggi), adesso) for g in gruppi)
    for g in gruppi:
        if g["start"] and g["start"] <= quando and (g["end"] is None or g["end"] >= quando):
            return compatibili(lato(g["grp"], quando), adesso)
    return True


# ---------- profili, in memoria ----------

@dataclass
class Profili:
    persone: dict[str, dict]                      # uri canonico -> profilo
    alias: dict[str, str]                         # ogni uri della persona -> uri canonico
    gruppi: dict[str, dict]                       # uri del gruppo o della componente -> nome, tipo, ramo
    organi: dict[str, dict]                       # uri dell'organo -> nome, ramo, tipo, tematico, parole chiave
    parole: dict[str, str] = field(default_factory=dict)      # uri dell'organo -> vettore delle parole chiave (letterale)
    schieramenti: maggioranza.Schieramenti | None = None          # la regola di maggioranza.py
    caricati: float = field(default_factory=time.monotonic)
    _lati: dict = field(default_factory=dict)

    def lato(self, grp: str | None, il: dt.date | None = None) -> str:
        """Maggioranza, opposizione o misto alla data (oggi, se manca), con la regola di maggioranza.py."""
        if grp == GOVERNO:
            return MAGGIORANZA
        if not self.gruppi.get(grp or "") or self.schieramenti is None:
            return OPPOSIZIONE
        il = il or dt.date.today()
        k = (grp, il.year, il.month)                 # basta il mese: le fiducie sono qualche decina l'anno
        if k not in self._lati:
            self._lati[k] = self.schieramenti.lato(grp, il)
        return self._lati[k]


_profili: Profili | None = None
_blocco = threading.Lock()


SQL_PERSONE = """
WITH coinvolti AS (                     -- chi ha un mandato nella legislatura o un incarico in un governo della legislatura
  SELECT person AS uri FROM mandate WHERE legislature = %(leg)s
  UNION SELECT o.person FROM office o JOIN government g ON o.target = g.uri OR o.target LIKE g.uri || ':%%'
  WHERE g.end_date IS NULL OR g.start_date >= (SELECT min(start_date) FROM mandate WHERE legislature = %(leg)s)),
tutti AS (SELECT uri FROM coinvolti UNION SELECT s.same_as FROM person_same_as s JOIN coinvolti c ON c.uri = s.person
          UNION SELECT s.person FROM person_same_as s JOIN coinvolti c ON c.uri = s.same_as)
SELECT p.uri, p.stub, p.given_name, p.family_name, p.photo, p.profession, p.education, p.camera_id, p.senato_id, p.source_uri
FROM tutti t JOIN person p ON p.uri = t.uri"""


def _carica_profili(c: psycopg.Connection) -> Profili:
    t0 = time.perf_counter()
    righe = {r["uri"]: r for r in c.execute(SQL_PERSONE, {"leg": LEGISLATURA})}
    # la stessa persona con più schede (senatori con la scheda della Camera): una sola voce, sotto l'uri che ha il mandato
    # più recente nella legislatura
    legami: dict[str, set[str]] = {u: {u} for u in righe}
    for r in c.execute("SELECT person, same_as FROM person_same_as"):
        if r["person"] in righe and r["same_as"] in righe:
            unione = legami[r["person"]] | legami[r["same_as"]]
            for u in unione:
                legami[u] = unione
    mandati: dict[str, list[dict]] = {}
    for r in c.execute("SELECT person, chamber, start_date, end_date FROM mandate WHERE legislature = %s", (LEGISLATURA,)):
        mandati.setdefault(r["person"], []).append({"chamber": r["chamber"], "start": r["start_date"], "end": r["end_date"]})
    alias: dict[str, str] = {}
    for gruppo in {frozenset(s) for s in legami.values()}:
        canonico = max(gruppo, key=lambda u: (max((m["start"] for m in mandati.get(u, [])), default=dt.date.min),
                                             not righe[u]["stub"], u))
        for u in gruppo:
            alias[u] = canonico

    gruppi = {r["uri"]: dict(r) for r in c.execute(
        "SELECT uri, chamber, kind, name, short_name, part_of FROM grp WHERE legislature = %s", (LEGISLATURA,))}
    organi = {}
    for r in c.execute("SELECT uri, chamber, kind, name, end_date FROM body WHERE legislature = %s", (LEGISLATURA,)):
        lungo, parole = temi_organo(r["name"])
        organi[r["uri"]] = {**r, "display": lungo or r["name"], "keywords": parole, "topical": tematico(r["name"])}

    persone: dict[str, dict] = {}
    for u, r in righe.items():
        p = persone.setdefault(alias[u], {"uri": alias[u], "schede": set(), "mandati": [], "gruppi": [], "sedi": [],
                                          "cariche": [], "governo": [], "profession": None, "education": None})
        p["schede"].add(u)
        p["mandati"] += mandati.get(u, [])
        principale = u == alias[u] or p.get("given_name") is None
        for k in ("given_name", "family_name", "photo", "camera_id", "senato_id", "source_uri"):
            if r[k] and (principale or not p.get(k)):
                p[k] = r[k]
        for k in ("profession", "education"):
            p[k] = p[k] or r[k]
    uris = list(righe)
    for r in c.execute("""SELECT m.person, m.grp, m.start_date, m.end_date FROM membership m JOIN grp g ON g.uri = m.grp
                          WHERE g.legislature = %s AND m.person = ANY(%s) ORDER BY m.start_date""", (LEGISLATURA, uris)):
        persone[alias[r["person"]]]["gruppi"].append({"grp": r["grp"], "start": r["start_date"], "end": r["end_date"]})
    for r in c.execute("SELECT person, body, start_date, end_date FROM seat WHERE person = ANY(%s)", (uris,)):
        if r["body"] in organi:
            persone[alias[r["person"]]]["sedi"].append({"body": r["body"], "start": r["start_date"], "end": r["end_date"]})
    for r in c.execute("SELECT person, target, title, title_raw, start_date, end_date FROM office WHERE person = ANY(%s)", (uris,)):
        p = persone[alias[r["person"]]]
        if r["target"] in organi:
            p["cariche"].append({"title": r["title"], "body": r["target"], "body_name": organi[r["target"]]["display"],
                                 "start": r["start_date"], "end": r["end_date"]})
        elif r["target"].startswith("it:gov:"):
            p["governo"].append({"title": r["title"], "label": r["title_raw"], "start": r["start_date"], "end": r["end_date"]})
    for p in persone.values():
        p["rami"] = {m["chamber"] for m in p["mandati"]}
        # il Senato non pubblica l'istruzione: per i senatori manca alla fonte, non è un titolo che manca
        p["senza_istruzione"] = not p["education"] and "senato" in p["rami"]
        p["nome"] = " ".join(x for x in (p.get("given_name"), p.get("family_name")) if x) or p["uri"]
    log.info("profili: %d persone, %d organi in %.0f ms", len(persone), len(organi), (time.perf_counter() - t0) * 1000)
    return Profili(persone=persone, alias=alias, gruppi=gruppi, organi=organi, schieramenti=maggioranza.carica(c))


def profili(c: psycopg.Connection) -> Profili:
    """I profili in memoria; dopo sei ore si rileggono (la prima volta chi chiede aspetta, poi no)."""
    global _profili
    p = _profili
    if p and time.monotonic() - p.caricati < DURATA_PROFILI:
        return p
    with _blocco:
        if _profili and time.monotonic() - _profili.caricati < DURATA_PROFILI:
            return _profili
        nuovi = _carica_profili(c)
        if p:
            nuovi.parole = p.parole                       # le parole chiave non cambiano: niente nuova chiamata
        _profili = nuovi
        return nuovi


def _vettori_parole(pr: Profili, ip: str | None) -> dict[str, str]:
    """I vettori delle parole chiave delle commissioni, una chiamata sola per processo. Se il modello non risponde si usa
    il nome dell'organo, e si riprova alla prossima domanda."""
    mancano = [u for u, o in pr.organi.items() if o["keywords"] and u not in pr.parole]
    if mancano:
        try:
            vv = modello.vettori([" ".join(pr.organi[u]["keywords"]) for u in mancano], ip)
            pr.parole.update({u: modello.letterale(v) for u, v in zip(mancano, vv)})
        except modello.ModelloNonDisponibile as e:
            log.warning("vettori delle parole chiave delle commissioni non disponibili: %s", e)
    return pr.parole


def gruppo_alla_data(p: dict, il: dt.date, pr: Profili) -> str | None:
    """Il gruppo (uri) alla data, con la componente del Misto prima del Misto; GOVERNO per chi è al governo senza seggio.
    Chi ha finito il mandato resta col gruppo dell'ultimo giorno."""
    if not p["mandati"] and p["governo"]:
        return GOVERNO
    fine = max((m["end"] or il for m in p["mandati"]), default=il)
    il = min(il, fine)
    attivi = [g for g in p["gruppi"] if attivo(g["start"], g["end"], il)]
    if not attivi:
        return None
    attivi.sort(key=lambda g: pr.gruppi.get(g["grp"], {}).get("kind") != "misto_component")
    return attivi[0]["grp"]


def nome_gruppo(grp: str | None, pr: Profili) -> str:
    """Il nome da mostrare: la componente del Misto col suo nome, mai «Misto» per chi ne fa parte."""
    if grp == GOVERNO:
        return GOVERNO
    g = pr.gruppi.get(grp or "")
    return g["name"] if g else "Misto"


# ---------- evidenze sul tema ----------

SQL_INTERVENTI = """
SELECT s.person, s.uri AS item, st.date, st.chamber, s.as_office, 1 - (v.embedding <=> %(q)s::halfvec(1024)) AS score
FROM passage p JOIN passage_vector v ON v.hash = p.hash AND v.model = %(m)s
JOIN speech s ON s.uri = p.uri JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
WHERE p.source = 'speech' AND st.kind = 'assembly_verbatim' AND st.chamber = ANY(%(rami)s) AND s.person IS NOT NULL
  AND (%(da)s::date IS NULL OR st.date >= %(da)s) AND (%(a)s::date IS NULL OR st.date <= %(a)s)
ORDER BY v.embedding <=> %(q)s::halfvec(1024) LIMIT %(k)s"""

# il gruppo alla data di ogni (persona, data) dei brani: a parte, perché la ricerca dei vicini può girare con
# enable_sort spento (vedi _in_parallelo) e group_at ha bisogno del suo ordinamento
SQL_GRUPPO_ALLA_DATA = "SELECT x.p, x.d, group_at(x.p, x.d) AS grp FROM unnest(%s::text[], %s::date[]) AS x(p, d)"

# atti di sindacato e indirizzo per il testo (il titolo è un'etichetta uguale per tutti), progetti di legge per il titolo
SQL_ATTI = """
SELECT x.item, x.date, x.score, sp.person, sp.first FROM (
  SELECT a.uri AS item, a.date, 1 - (v.embedding <=> %(q)s::halfvec(1024)) AS score
  FROM passage p JOIN passage_vector v ON v.hash = p.hash AND v.model = %(m)s JOIN act a ON a.uri = p.uri
  WHERE p.source = %(fonte)s AND a.chamber = ANY(%(rami)s) AND a.legislature = %(leg)s
    AND (%(da)s::date IS NULL OR a.date >= %(da)s) AND (%(a)s::date IS NULL OR a.date <= %(a)s)
  ORDER BY v.embedding <=> %(q)s::halfvec(1024) LIMIT %(k)s) x
JOIN act_sponsor sp ON sp.act = x.item"""

SQL_PROFILI = """
SELECT p.source, p.uri, max(1 - (v.embedding <=> %(q)s::halfvec(1024))) AS sim
FROM passage p JOIN passage_vector v ON v.hash = p.hash AND v.model = %(m)s
WHERE p.source IN ('profession', 'education', 'body') GROUP BY 1, 2"""


_indice: tuple[float, bool] = (0.0, False)


def con_indice(c: psycopg.Connection) -> bool:
    """Se l'indice HNSW su passage_vector c'è ed è valido (si ricontrolla ogni dieci minuti)."""
    global _indice
    if time.monotonic() - _indice[0] > 600:
        r = c.execute("""SELECT bool_or(i.indisvalid) AS ok FROM pg_index i JOIN pg_class x ON x.oid = i.indexrelid
                         WHERE x.relname = 'passage_vector_hnsw'""").fetchone()
        _indice = (time.monotonic(), bool(r and r["ok"]))
    return _indice[1]


def _prepara(c: psycopg.Connection, indice: bool) -> None:
    """Con l'indice: la ricerca HNSW continua finché i filtri non lasciano abbastanza righe. Senza: una lettura di tutti i
    vettori con hash join (il nested loop legge i vettori uno per uno ed è tre volte più lento), senza processi paralleli,
    che con più memoria per l'hash riempiono la memoria condivisa del container."""
    c.execute(f"SET statement_timeout = '{TEMPO_MASSIMO}'")
    if indice:
        c.execute("SET hnsw.ef_search = 1000")
        c.execute("SET hnsw.iterative_scan = 'relaxed_order'")
        c.execute("SET hnsw.max_scan_tuples = 200000")
    else:
        c.execute("SET enable_nestloop = off")
        c.execute("SET work_mem = '64MB'")
        c.execute("SET max_parallel_workers_per_gather = 0")


def _ripristina(c: psycopg.Connection) -> None:
    for k in ("statement_timeout", "enable_nestloop", "work_mem", "max_parallel_workers_per_gather", "hnsw.ef_search",
              "hnsw.iterative_scan", "hnsw.max_scan_tuples"):
        c.execute(f"RESET {k}")


def _ampia(rami: list[str], da: dt.date | None, a: dt.date | None) -> bool:
    """Vero se i filtri della ricerca dei brani d'Aula lasciano tanti vettori (l'Aula della Camera, il 12% dei brani, senza
    date): allora l'indice HNSW trova i 2.000 vicini in 1-3 secondi, ma il planner sottostima quanti brani passano il
    filtro su sedute e ramo e sceglie la lettura esatta, 4-10 secondi. Con l'Aula del Senato sola (5%) o con le date
    l'indice si ferma a hnsw.max_scan_tuples prima di trovarli tutti: lì la lettura esatta è giusta (EXPLAIN ANALYZE del
    4/11/2026, benchmark/pilota-2026-11-04)."""
    return "camera" in rami and da is None and a is None


def _in_parallelo(c: psycopg.Connection, lavori: dict[str, tuple[str, dict]]) -> tuple[dict[str, list[dict]], list[str]]:
    """Le query delle evidenze, ognuna con la sua connessione (se se ne possono aprire altre, se no una dopo l'altra su
    `c`). Una ricerca che fallisce non ferma la classifica: dà nessuna riga e il suo nome torna fra quelle fallite."""
    from ..db import connessione
    indice = con_indice(c)

    SENZA = object()                                          # non si è potuta aprire un'altra connessione

    def una(nome: str, sql: str, par: dict, conn: psycopg.Connection | None = None):
        if conn is None:
            try:
                conn = connessione()
            except psycopg.Error:
                return nome, SENZA
            with conn:
                _prepara(conn, indice)
                return una(nome, sql, par, conn)
        try:
            par = dict(par)
            with conn.transaction():
                if par.pop("_ampia", False) and indice:     # vedi _ampia: l'indice anche quando il planner non lo sceglie
                    conn.execute("SET LOCAL enable_sort = off")
                return nome, conn.execute(sql, par).fetchall()
        except psycopg.Error as e:
            log.error("ricerca delle evidenze %s non riuscita: %s", nome, type(e).__name__)
            return nome, None

    _prepara(c, indice)
    try:
        with ThreadPoolExecutor(max_workers=len(lavori)) as pool:
            esiti = dict(pool.map(lambda kv: una(kv[0], *kv[1]), lavori.items()))
        for n in [n for n, r in esiti.items() if r is SENZA]:  # sulla connessione data, una dopo l'altra
            esiti[n] = una(n, *lavori[n], c)[1]
    finally:
        _ripristina(c)
    return {n: r or [] for n, r in esiti.items()}, [n for n, r in esiti.items() if r is None]


@dataclass
class Evidenze:
    interventi: list[dict]
    atti: list[dict]
    titoli: list[dict]
    profili: list[dict]
    fallite: list[str]
    quando: float = field(default_factory=time.monotonic)


_evidenze: OrderedDict[tuple, Evidenze] = OrderedDict()
_vettori: OrderedDict[str, str] = OrderedDict()
MASSIMO_IN_MEMORIA = 50


def _ricorda(cache: OrderedDict, chiave, valore) -> None:
    cache[chiave] = valore
    cache.move_to_end(chiave)
    while len(cache) > MASSIMO_IN_MEMORIA:
        cache.popitem(last=False)


def vettore(domanda: str, ip: str | None = None) -> str:
    """Il vettore della domanda come letterale halfvec, in memoria per le domande ripetute. Solleva
    modello.ModelloNonDisponibile se il modello non risponde."""
    k = " ".join(domanda.lower().split())
    if k not in _vettori:
        _ricorda(_vettori, k, modello.letterale(modello.vettori([domanda], ip)[0]))
    return _vettori[k]


def _rami(ambito) -> list[str]:
    rami = list(getattr(ambito, "rami", None) or RAMI) if ambito is not None else list(RAMI)
    return [r for r in RAMI if r in rami] or list(RAMI)


def evidenze(c: psycopg.Connection, q: str, rami: list[str], da: dt.date | None = None, a: dt.date | None = None) -> Evidenze:
    """Le tre ricerche dei vicini e le somiglianze dei profili, per un vettore e un ambito, in memoria: la classifica e
    la verifica della stessa domanda le usano tutte e due."""
    chiave = (q, tuple(rami), da, a)
    e = _evidenze.get(chiave)
    if e and (not e.fallite or time.monotonic() - e.quando < 60):     # con ricerche fallite si riprova dopo un minuto
        _evidenze.move_to_end(chiave)
        return e
    base = {"q": q, "m": modello.MODELLO_VETTORI, "rami": rami, "da": da, "a": a, "leg": LEGISLATURA}
    righe, fallite = _in_parallelo(c, {
        "interventi": (SQL_INTERVENTI, {**base, "k": K_BRANI, "_ampia": _ampia(rami, da, a)}),
        "atti": (SQL_ATTI, {**base, "fonte": "act", "k": K_ATTI}),
        "titoli": (SQL_ATTI, {**base, "fonte": "act_title", "k": K_ATTI}),
        "profili": (SQL_PROFILI, base)})
    coppie = sorted({(r["person"], r["date"]) for r in righe["interventi"]})
    if coppie:
        gruppi = {(r["p"], r["d"]): r["grp"] for r in c.execute(SQL_GRUPPO_ALLA_DATA, ([p for p, _ in coppie], [d for _, d in coppie]))}
        for r in righe["interventi"]:
            r["grp"] = gruppi.get((r["person"], r["date"]))
    e = Evidenze(righe["interventi"], righe["atti"], righe["titoli"], righe["profili"], fallite)
    _ricorda(_evidenze, chiave, e)
    return e


# ---------- punteggi ----------

def popolazione(pr: Profili, rami: Iterable[str]) -> set[str]:
    """Chi conta per le componenti relative: chi ha un mandato in uno dei rami, o nessun mandato (governo da fuori)."""
    voluti = set(rami)
    return {u for u, p in pr.persone.items() if (p["rami"] & voluti) or (not p["rami"] and p["governo"])}


def _somiglianze(e: Evidenze, pr: Profili, q: str, c: psycopg.Connection, rami: list[str], pop: set[str],
                 ip: str | None) -> tuple[dict, dict, dict]:
    prof, istr, nomi = {}, {}, {}
    for r in e.profili:
        if r["source"] == "body":
            nomi[r["uri"]] = r["sim"]
            continue
        u = pr.alias.get(r["uri"])
        if u in pop:
            d = prof if r["source"] == "profession" else istr
            d[u] = max(d.get(u, -1.0), r["sim"])
    parole = _vettori_parole(pr, ip)
    voluti = set(rami)
    tematici = [u for u, o in pr.organi.items() if o["topical"] and (o["chamber"] in voluti or o["kind"] == "bicameral_committee")]
    con_parole = [u for u in tematici if u in parole]
    simili = {}
    if con_parole:
        for r in c.execute("SELECT k, 1 - (e::halfvec(1024) <=> %s::halfvec(1024)) AS sim FROM unnest(%s::text[], %s::text[]) AS t(k, e)",
                           (q, con_parole, [parole[u] for u in con_parole])):
            simili[r["k"]] = r["sim"]
    for u in tematici:
        if u not in simili and u in nomi:
            simili[u] = nomi[u]
    # parole chiave e nomi hanno la stessa fascia di coseni: si mettono in fila insieme, mediana 0, il migliore 1
    return relativo_simile(prof), relativo_simile(istr), relativo_simile(simili, 50, 100)


def punteggi(c: psycopg.Connection, domanda: str, ambito=None, persone: list[str] | None = None, pesi: dict | None = None,
             ip: str | None = None, riferimento: dt.date | None = None) -> list[dict]:
    """Una voce per parlamentare (o membro del governo) con le sei componenti e il punteggio, ordinate dal più alto.

    `ambito` ha `rami`, `da`, `a` (come recupero.Ambito; None: tutti e due i rami, tutta la legislatura): le evidenze e le
    popolazioni sono quelle dei rami dell'ambito, nel periodo; il giorno di riferimento è `a` (o oggi). `persone`: uri
    (anche la seconda scheda della persona) di chi tenere; None: tutti quelli dei rami. `pesi`: i pesi scelti da chi
    chiede, riportati alla scala del modello.

    Ogni voce: uri (quello chiesto), canonico (l'uri della persona, una per tutte le sue schede), nome, rami, gruppo
    (uri; GOVERNO per chi è al governo senza seggio), voce (nome del gruppo o della componente del Misto), coalizione,
    componenti (le sei, con le chiavi di COMPONENTI), punteggio, rango e nel_gruppo (posizione e quanti nella stessa
    voce fra quelli restituiti), carica, disponibile, degradato (le ricerche fallite, se ce ne sono).

    Solleva modello.ModelloNonDisponibile se il vettore della domanda non si può calcolare."""
    t0 = time.perf_counter()
    rami = _rami(ambito)
    da, a = getattr(ambito, "da", None), getattr(ambito, "a", None)
    oggi = dt.date.today()
    riferimento = riferimento or min(a or oggi, oggi)
    scelti = pesi_richiesta(pesi) or dict(PESI)
    q = vettore(domanda, ip)
    pr = profili(c)
    e = evidenze(c, q, rami, da, a)
    pop = popolazione(pr, rami)

    attuali = {u: gruppo_alla_data(p, riferimento, pr) for u, p in pr.persone.items()}

    def vale(sid: str, quando: dt.date | None) -> bool:
        p = pr.persone.get(sid)
        return p is None or valida(p["gruppi"], pr.lato, attuali.get(sid), quando, riferimento)

    def riga(r: dict) -> dict:
        return {**r, "sid": pr.alias.get(r["person"], r["person"])}

    interventi = relativo_log(pesi_tema(map(riga, e.interventi), riferimento, EMIVITA_INTERVENTI, vale, SENZA_DATA))
    firma = lambda r: PRIMO if r["first"] else COFIRMATARIO              # noqa: E731
    atti = pesi_tema(map(riga, e.atti), riferimento, EMIVITA_ATTI, vale, SENZA_DATA, firma)
    for sid, w in pesi_tema(map(riga, e.titoli), riferimento, EMIVITA_ATTI, vale, SENZA_DATA, firma).items():
        atti[sid] = atti.get(sid, 0.0) + w             # testi e titoli hanno ognuno la sua scala: si sommano i pesi
    atti = relativo_log(atti)
    professione, istruzione, pertinenza = _somiglianze(e, pr, q, c, rami, pop, ip)

    if persone is None:
        scelte = [(u, u) for u in sorted(pop)]
    else:                                              # ogni uri chiesto torna com'è, anche la seconda scheda
        scelte = [(u, pr.alias.get(u, u)) for u in dict.fromkeys(persone)]
    out = []
    for chiesto, u in scelte:
        p = pr.persone.get(u)
        if p is None:
            out.append({"uri": chiesto, "canonico": u, "nome": None, "rami": [], "gruppo": None, "voce": None, "coalizione": None,
                        "componenti": {}, "punteggio": 0.0, "carica": None, "disponibile": False})
            continue
        ruolo, carica = punteggio_ruolo(p["governo"], p["cariche"], pertinenza, riferimento)
        comp = {"profession": professione.get(u, 0.0), "education": istruzione.get(u, 0.0),
                "committee": punteggio_commissione(p["sedi"], pertinenza, riferimento), "acts": atti.get(u, 0.0),
                "interventions": interventi.get(u, 0.0), "role": ruolo}
        comp = {k: min(v, TETTO) for k, v in comp.items()}
        w = pesi_persona(p["senza_istruzione"], scelti)
        g = attuali.get(u)
        out.append({"uri": chiesto, "canonico": u, "nome": p["nome"], "rami": sorted(p["rami"]), "gruppo": g, "voce": nome_gruppo(g, pr),
                    "coalizione": pr.lato(g, riferimento) if g != GOVERNO else "governo", "componenti": comp,
                    "punteggio": max(0.0, min(1.0, sum(w[k] * v for k, v in comp.items()))), "carica": carica,
                    "disponibile": True, **({"degradato": e.fallite} if e.fallite else {})})
    out.sort(key=lambda x: -x["punteggio"])
    per_voce: dict[str | None, list[dict]] = {}
    for x in out:
        per_voce.setdefault(x["voce"], []).append(x)
    for xs in per_voce.values():
        for i, x in enumerate(xs, 1):
            x["rango"], x["nel_gruppo"] = i, len(xs)
    if e.fallite:
        log.error("autorevolezza DEGRADATA: ricerche non riuscite %s", ", ".join(e.fallite))
    log.info("autorevolezza: %d voci, %d brani, %d firme, %.0f ms", len(out), len(e.interventi), len(e.atti) + len(e.titoli),
             (time.perf_counter() - t0) * 1000)
    return out


# ---------- la classifica del sito ----------

def id_sito(p: dict, ramo: str) -> str:
    """L'id della voce nella forma che legge il sito: la scheda di dati.camera.it (…/persona.rdf/p300469) per i deputati,
    di dati.senato.it (…/senatore/36449) per i senatori."""
    if ramo == "senato" and p.get("senato_id"):
        return f"http://dati.senato.it/senatore/{p['senato_id']}"
    if p.get("camera_id"):
        return f"http://dati.camera.it/ocd/persona.rdf/p{p['camera_id']}"
    return p["uri"]


_classifiche: OrderedDict[tuple, dict] = OrderedDict()


@dataclass
class _Ramo:
    rami: tuple
    da: dt.date | None = None
    a: dt.date | None = None


def classifica(c: psycopg.Connection, tema: str, ramo: str = "camera", pesi: dict | None = None,
               ip: str | None = None) -> dict:
    """Tutti i deputati (o i senatori) per autorevolezza sul tema, nella forma della vecchia /api/authority-ranking:
    {topic, count, computation_time_ms, deputies: [{id, first_name, last_name, group, coalition, authority_score,
    score_breakdown, photo, camera_profile_url, profession, education, committee, committees, institutional_role}]}.
    In memoria per tema; `cached` è vero quando la classifica non si è rifatta."""
    chiave = (" ".join(tema.lower().split()), ramo, json.dumps(pesi_richiesta(pesi), sort_keys=True))
    if chiave in _classifiche:
        _classifiche.move_to_end(chiave)
        return {**_classifiche[chiave], "cached": True}
    t0 = time.perf_counter()
    voci = punteggi(c, tema, _Ramo((ramo,)), pesi=pesi, ip=ip)
    pr = profili(c)
    oggi = dt.date.today()
    deputati = []
    for v in voci:
        p = pr.persone[v["uri"]]
        if ramo not in p["rami"]:
            continue
        comp = v["componenti"]
        sedi = [pr.organi[s["body"]]["display"] for s in p["sedi"] if attivo(s["start"], s["end"], oggi)]
        deputati.append({
            "id": id_sito(p, ramo), "first_name": p.get("given_name") or "", "last_name": p.get("family_name") or "",
            "group": v["voce"], "coalition": v["coalizione"], "authority_score": round(v["punteggio"], 4),
            "score_breakdown": {"speeches": round(comp["interventions"], 4), "acts": round(comp["acts"], 4),
                                "committee": round(comp["committee"], 4), "profession": round(comp["profession"], 4),
                                "education": round(comp["education"], 4), "role": round(comp["role"], 4)},
            "photo": p.get("photo"),
            "camera_profile_url": f"https://www.camera.it/deputati/elenco/19-{p['camera_id']}" if ramo == "camera" and p.get("camera_id") else None,
            "profession": p["profession"], "education": p["education"],
            "committee": sedi[0] if sedi else None, "committees": sedi, "institutional_role": v["carica"],
            **({"degraded": v["degradato"]} if v.get("degradato") else {})})
    out = {"topic": tema, "count": len(deputati), "computation_time_ms": round((time.perf_counter() - t0) * 1000),
           "deputies": deputati}
    if not any(d.get("degraded") for d in deputati):
        _ricorda(_classifiche, chiave, out)
    return out
