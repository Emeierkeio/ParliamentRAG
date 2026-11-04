"""Verifica delle tre garanzie su una risposta in testo libero, scritta da qualunque sistema, portata dal backend
precedente sul Postgres v3. Per ogni risposta dice:

1. Citazioni esatte: ogni testo tra «…» si cerca negli interventi (strumenti/citazioni.py, lo stesso controllo della
   chat). Passa solo se è un tratto di un intervento parola per parola; con i tagli («a … b») è «omissions».
2. Tutti i gruppi: ogni gruppo in carica, ogni componente del Misto con membri e il Governo devono essere nominati o
   citati. Una voce senza nessuno che abbia parlato del tema è «silent»: l'esito è «warn», non «fail», quando mancano
   solo le voci mute.
3. Voci autorevoli: per ogni citazione esatta, e per ogni parlamentare o membro del governo nominato, la posizione sul
   tema. È autorevole il Governo, il relatore, o chi sta fra i primi AUTOREVOLI_PRIMI del suo gruppo per autorevolezza,
   in classifica fra chi del gruppo ha parlato del tema (speakers_on_topic), non fra tutti i membri.

Chi ha parlato del tema: chi ha un brano fra i 100 interventi d'Aula più vicini alla domanda, e per ogni gruppo (o
componente) chi ha un brano fra i 20 più vicini del gruppo, col gruppo alla data dell'intervento. Il testo della
risposta non si scrive da nessuna parte."""

from __future__ import annotations

import datetime as dt
import logging
import re
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field

import psycopg

from ..strumenti import citazioni
from ..strumenti.comune import LEGISLATURA, RAMI
from . import autorevolezza as A
from . import modello

log = logging.getLogger("parliamentrag.fascicolo.verifica")

AUTOREVOLI_PRIMI = 5
PRIMI_VICINI = 100                # gli oratori dei primi brani: le evidenze di chi risponde
PER_GRUPPO = 20                   # i brani più vicini di ogni gruppo: il perimetro di chi ha parlato del tema
SOGLIA_PERIMETRO = 0.15
TEMA_DALLA_RISPOSTA = 200         # senza domanda, il tema è l'inizio della risposta senza le citazioni
POOL_SUL_TEMA, POOL_GRUPPO = "speakers_on_topic", "group_members"
DURATA_ELENCHI = 3600             # chi è in carica cambia con i passaggi di gruppo e i rimpasti

APOSTROFI = "'’‘`´ʼ"
_APOSTROFI = re.compile("[" + APOSTROFI + "]")
_CITAZIONE = re.compile(r"«([^«»]+)»")
GOVERNO_RE = re.compile(r"^(ministr|vice ?ministr|sottosegretari|presidente del consiglio|vice ?presidente del consiglio)", re.I)
RELATORE_RE = re.compile(r"^relat(ore|rice)", re.I)
_GRAVE = {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù", "A": "À", "E": "È", "I": "Ì", "O": "Ò", "U": "Ù"}


def nome_camera(nome: str | None) -> str:
    """I resoconti della Camera scrivono l'accento finale con l'apostrofo (URZI'): si rimette l'accento (Urzì)."""
    return re.sub(r"([AEIOUaeiou])'(?=\s|$)", lambda m: _GRAVE[m.group(1)], (nome or "").strip())


def _piega(t: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", t) if unicodedata.category(ch) != "Mn").lower()


def _piega_uguale(t: str) -> str:
    """Minuscolo senza accenti, un carattere per un carattere (le posizioni restano quelle del testo)."""
    return "".join(unicodedata.normalize("NFD", ch)[0] for ch in _APOSTROFI.sub("'", t)).lower()


def nominato_vicino(risposta: str, inizio: int, fine: int, cognome: str, prima: int = 220, dopo: int = 100) -> bool:
    """Il cognome di chi parla è scritto vicino alla citazione?"""
    if not cognome:
        return False
    intorno = _piega(risposta[max(0, inizio - prima): fine + dopo])
    return re.search(r"(^|[^\w])" + re.escape(_piega(cognome)) + r"($|[^\w])", intorno) is not None


def ruolo_nel_dibattito(as_office: str | None, al_governo: bool) -> str | None:
    """'governo' | 'relatore' | None, dalla qualifica scritta dopo il nome di chi parla."""
    if as_office and GOVERNO_RE.match(as_office):
        return "governo"
    if as_office and RELATORE_RE.match(as_office):
        return "relatore"
    return "governo" if al_governo else None


# ---------- le voci: gruppi, componenti del Misto, Governo ----------

MISTO_SENZA_COMPONENTE = "Misto (non iscritto a una componente)"


def etichetta_gruppo(gruppo: str | None, componente: str | None) -> str:
    """Il nome di un gruppo senza voce: la componente, o il membro del Misto senza componente, mai «Misto» da solo."""
    if componente:
        return componente.title()
    if not gruppo or gruppo.strip().upper() == "MISTO":
        return MISTO_SENZA_COMPONENTE
    return gruppo.title()


@dataclass
class Voce:
    """Un gruppo, una componente del Misto o il Governo, con i nomi che valgono come menzione. Le sigle contano solo
    scritte così (FI, Lega, Azione): «lega la proposta» o «un'azione» non contano; i nomi interi in ogni forma."""
    key: str
    label: str
    kind: str                     # group | component | government
    match: str = ""               # pezzo del nome nel database, in maiuscolo
    abbreviations: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    chamber: str | None = None    # voce che c'è in un ramo solo


VOCI: list[Voce] = [
    Voce("FdI", "Fratelli d'Italia", "group", "FRATELLI D'ITALIA", ["FdI", "FDI"], ["Fratelli d'Italia", "Brothers of Italy"]),
    Voce("PD", "Partito Democratico", "group", "PARTITO DEMOCRATICO", ["PD", "Pd"],
         ["Partito Democratico", "Italia Democratica e Progressista", "Democratic Party"]),
    Voce("Lega", "Lega - Salvini Premier", "group", "LEGA", ["Lega", "League"], ["Lega Salvini", "Salvini Premier"]),
    Voce("M5S", "Movimento 5 Stelle", "group", "MOVIMENTO 5 STELLE", ["M5S"],
         ["Movimento 5 Stelle", "Movimento Cinque Stelle", "5 Stelle", "Cinque Stelle", "Five Star Movement", "Five Stars"]),
    Voce("FI", "Forza Italia", "group", "FORZA ITALIA", ["FI"], ["Forza Italia", "Forward Italy", "Go Italy"]),
    Voce("AVS", "Alleanza Verdi e Sinistra", "group", "ALLEANZA VERDI E SINISTRA", ["AVS"],
         ["Alleanza Verdi e Sinistra", "Verdi e Sinistra", "Greens and Left Alliance", "Green and Left Alliance"]),
    Voce("Azione", "Azione - PER", "group", "AZIONE", ["Azione", "AZ", "Action"], ["Popolari Europeisti Riformatori"]),
    Voce("IV", "Italia Viva - Casa Riformista", "group", "ITALIA VIVA", ["IV", "IV-CR"], ["Italia Viva", "Casa Riformista", "Italy Alive"]),
    Voce("NM", "Noi Moderati", "group", "NOI MODERATI", ["NM"], ["Noi Moderati", "MAIE", "Centro Popolare", "Us Moderates"]),
    Voce("+Europa", "+Europa (Misto)", "component", "+EUROPA", ["+Europa"], ["Più Europa", "+ Europa", "More Europe"]),
    Voce("FN", "Futuro Nazionale Vannacci (Misto)", "component", "FUTURO NAZIONALE", ["FN"], ["Futuro Nazionale", "Vannacci"]),
    Voce("Min. ling.", "Minoranze linguistiche (Misto)", "component", "MINORANZE LINGUISTICHE", ["SVP"],
         ["Minoranze linguistiche", "Minoranze Linguistiche", "Südtiroler Volkspartei", "linguistic minorities"]),
    Voce("SCN", "Sud chiama Nord (Misto)", "component", "SUD CHIAMA NORD", [], ["Sud chiama Nord", "South Calls North"]),
    # Misto del Senato (le sue componenti AVS e Azione contano per quei gruppi)
    Voce("PSI", "Avanti PSI (Misto)", "component", "AVANTI PSI", ["PSI"], ["Avanti PSI", "Partito Socialista"], chamber="senato"),
    Voce("PRC", "Rifondazione Comunista (Misto)", "component", "RIFONDAZIONE COMUNISTA", ["PRC"],
         ["Rifondazione Comunista", "Rifondazione", "Open Sinistra"], chamber="senato"),
    Voce("ID-MR", "Italia Domani - Marco Rizzo (Misto)", "component", "ITALIA DOMANI", ["ID-MR"], ["Italia Domani"],
         chamber="senato"),
    Voce("Autonomie", "Per le Autonomie (SVP-PATT, Campobase)", "group", "PER LE AUTONOMIE", [],
         ["Per le Autonomie", "Autonomie", "Campobase", "SVP-PATT"], chamber="senato"),
    # chi sta nel Misto senza una componente (alla Camera i non iscritti, al Senato anche i senatori a vita)
    Voce("Misto NI", "Misto, non iscritti", "component", "", [], ["non iscritti", "non iscritto", "non iscritta",
         "senatori a vita", "senatore a vita", "senatrice a vita"]),
    Voce("Governo", "Governo", "government", "", [],
         ["Governo", "Esecutivo", "ministro", "ministra", "sottosegretario", "sottosegretaria", "Government", "minister",
          "undersecretary"]),
]
GOVERNO_VOCE = next(v for v in VOCI if v.kind == "government")
MISTO_NI = next(v for v in VOCI if v.key == "Misto NI")


def _maiuscolo(nome: str | None) -> str:
    return _APOSTROFI.sub("'", (nome or "").upper())


def voce_del_gruppo(gruppo: str | None, componente: str | None, al_governo: bool) -> Voce | None:
    """La voce di chi parla: il Governo, la componente del Misto o il gruppo. Una componente col nome di un gruppo conta
    per quel gruppo (al Senato AVS e Azione stanno nel Misto come componenti)."""
    if al_governo:
        return GOVERNO_VOCE
    if componente:
        for tipo in ("component", "group"):
            for v in VOCI:
                if v.kind == tipo and v.match and v.match in _maiuscolo(componente):
                    return v
    if gruppo and _maiuscolo(gruppo).strip() == "MISTO":
        return MISTO_NI
    if gruppo:
        for v in VOCI:
            if v.kind == "group" and v.match in _maiuscolo(gruppo):
                return v
    return None


def _trova(testo: str, alias: str, maiuscole: bool) -> str | None:
    m = re.search(r"(^|[^\w+])(" + re.escape(alias) + r")(?=$|[^\w])", testo, 0 if maiuscole else re.IGNORECASE)
    return m.group(2) if m else None


def nominata_come(risposta: str, v: Voce) -> str | None:
    """Come la risposta nomina la voce, o None."""
    testo = _APOSTROFI.sub("'", risposta)
    for a in v.abbreviations:
        if (x := _trova(testo, a, True)):
            return x
    for n in v.names:
        if (x := _trova(testo, _APOSTROFI.sub("'", n), False)):
            return x
    return None


# ---------- ambito ----------

_SENATO_RE = re.compile(r"\b(senato|senator[ei]|senatric[ei]|palazzo madama)\b", re.I)
_CAMERA_RE = re.compile(r"\b((all[ao']|nell[ao']|dell[ao']|in)\s*camera\b(?!\s+di\s+commercio)|camera dei deputati|deputat[ie]|montecitorio)", re.I)
_SEGNI_RAMO = {"camera": re.compile(r"camera\.it\b|(?<![\w])leg\d+_sed|it:camera:", re.I),
               "senato": re.compile(r"senato\.it\b|(?<![\w])sen_leg\d+_sed|it:senato:", re.I)}
ETICHETTE_AMBITO = {("camera",): "Camera dei deputati, XIX legislatura", ("senato",): "Senato della Repubblica, XIX legislatura",
                    ("camera", "senato"): "Camera dei deputati e Senato della Repubblica, XIX legislatura"}


def rami_nella_domanda(domanda: str) -> list[str]:
    trovati = {r for r, rx in (("senato", _SENATO_RE), ("camera", _CAMERA_RE)) if rx.search(domanda or "")}
    return [r for r in RAMI if r in trovati]


def rami_della_risposta(risposta: str, citate: list[dict]) -> list[str]:
    """I rami da cui la risposta attinge: gli interventi delle sue citazioni e i link ufficiali che scrive."""
    trovati = {q["speech"]["chamber"] for q in citate if q.get("speech")}
    trovati |= {r for r, rx in _SEGNI_RAMO.items() if rx.search(risposta or "")}
    return [r for r in RAMI if r in trovati]


def rami_attesi(rami: list[str], domanda: str, risposta: str, citate: list[dict]) -> tuple[list[str], str]:
    """I rami di cui la risposta deve sentire i gruppi, e perché. Senza modello: fra i rami chiesti, quello che nomina la
    domanda; altrimenti quello di tutte le citazioni e i link della risposta; altrimenti tutti."""
    if len(rami) <= 1:
        return rami, "request"
    nominati = [r for r in rami_nella_domanda(domanda) if r in rami]
    if len(nominati) == 1:
        return nominati, "question"
    visti = [r for r in rami_della_risposta(risposta, citate) if r in rami]
    if len(visti) == 1:
        return visti, "answer"
    return rami, "both"


# ---------- in carica: voci e persone ----------

_elenchi: dict[tuple, tuple[float, object]] = {}


def _in_memoria(chiave: tuple, calcola):
    t, v = _elenchi.get(chiave, (0.0, None))
    if v is None or time.monotonic() - t > DURATA_ELENCHI:
        v = calcola()
        _elenchi[chiave] = (time.monotonic(), v)
    return v


SQL_IN_CARICA = """
SELECT DISTINCT g.uri, g.name, g.kind, g.chamber, pg.name AS misto
FROM membership m JOIN grp g ON g.uri = m.grp LEFT JOIN grp pg ON pg.uri = g.part_of
WHERE m.end_date IS NULL AND g.legislature = %s AND g.chamber = ANY(%s)"""


# membri del Misto in carica senza una componente in carica
SQL_MISTO_NI = """
SELECT 1 FROM membership m JOIN grp g ON g.uri = m.grp
WHERE m.end_date IS NULL AND g.legislature = %s AND g.chamber = ANY(%s) AND g.kind <> 'misto_component' AND upper(g.name) = 'MISTO'
  AND NOT EXISTS (SELECT 1 FROM membership m2 JOIN grp c ON c.uri = m2.grp
                  WHERE m2.person = m.person AND m2.end_date IS NULL AND c.kind = 'misto_component' AND c.part_of = g.uri)
LIMIT 1"""


def voci_in_carica(c: psycopg.Connection, rami: list[str]) -> list[Voce]:
    """Le voci da cercare: i gruppi in carica nei rami, le componenti del Misto con membri, il Governo."""
    def calcola() -> list[Voce]:
        chiavi = set()
        if c.execute(SQL_MISTO_NI, (LEGISLATURA, rami)).fetchone():
            chiavi.add(MISTO_NI.key)
        for r in c.execute(SQL_IN_CARICA, (LEGISLATURA, rami)):
            if r["kind"] != "misto_component" and _maiuscolo(r["name"]).strip() == "MISTO":
                continue                             # il Misto conta per componente, e per i non iscritti qui sopra
            comp = r["kind"] == "misto_component"
            v = voce_del_gruppo(None if comp else r["name"], r["name"] if comp else None, False)
            if v:
                chiavi.add(v.key)
        return [v for v in VOCI if v.kind == "government" or v.key in chiavi]
    return _in_memoria(("voci", tuple(rami)), calcola)


@dataclass
class Persona:
    uri: str                       # uri canonico (autorevolezza.Profili.alias)
    given: str
    family: str
    gruppo: str | None             # nome del gruppo in carica
    componente: str | None         # nome della componente del Misto
    al_governo: bool
    ramo: str | None = None

    @property
    def nome(self) -> str:
        return f"{self.given} {self.family}".strip()

    @property
    def voce(self) -> Voce | None:
        return voce_del_gruppo(self.gruppo, self.componente, self.gruppo is None)


SQL_PERSONE = """
WITH gov AS (SELECT uri FROM government WHERE end_date IS NULL ORDER BY start_date DESC LIMIT 1),
al_governo AS (SELECT DISTINCT o.person FROM office o, gov WHERE (o.target = gov.uri OR o.target LIKE gov.uri || ':%%') AND o.end_date IS NULL),
in_carica AS (
  SELECT m.person, g.chamber, CASE WHEN g.kind = 'misto_component' THEN pg.name ELSE g.name END AS gruppo,
         CASE WHEN g.kind = 'misto_component' THEN g.name END AS componente,
         row_number() OVER (PARTITION BY m.person ORDER BY g.kind = 'misto_component' DESC) AS n
  FROM membership m JOIN grp g ON g.uri = m.grp LEFT JOIN grp pg ON pg.uri = g.part_of
  WHERE m.end_date IS NULL AND g.legislature = %(leg)s AND g.chamber = ANY(%(rami)s))
SELECT p.uri, p.given_name, p.family_name, x.chamber, x.gruppo, x.componente,
       (p.uri IN (SELECT person FROM al_governo)
        OR EXISTS (SELECT 1 FROM person_same_as s JOIN al_governo a ON a.person IN (s.person, s.same_as)
                   WHERE p.uri IN (s.person, s.same_as))) AS al_governo
FROM in_carica x JOIN person p ON p.uri = x.person WHERE x.n = 1
UNION ALL
SELECT p.uri, p.given_name, p.family_name, NULL, NULL, NULL, true
FROM al_governo a JOIN person p ON p.uri = a.person
WHERE NOT EXISTS (SELECT 1 FROM mandate m WHERE m.legislature = %(leg)s AND m.end_date IS NULL
                  AND m.person IN (SELECT a.person UNION SELECT same_as FROM person_same_as WHERE person = a.person
                                   UNION SELECT person FROM person_same_as WHERE same_as = a.person))"""


def persone_in_carica(c: psycopg.Connection, rami: list[str], pr: A.Profili) -> list[Persona]:
    """I parlamentari in carica nei rami e i membri del governo in carica (chi è al governo senza seggio parla per il
    Governo, non per un gruppo)."""
    def calcola() -> list[Persona]:
        per_uri: dict[str, Persona] = {}
        for r in c.execute(SQL_PERSONE, {"leg": LEGISLATURA, "rami": rami}):
            u = pr.alias.get(r["uri"], r["uri"])
            if u in per_uri:
                per_uri[u].al_governo = per_uri[u].al_governo or r["al_governo"]
                continue
            per_uri[u] = Persona(u, nome_camera(r["given_name"]), nome_camera(r["family_name"]), r["gruppo"],
                                 r["componente"], bool(r["al_governo"]), r["chamber"])
        return list(per_uri.values())
    return _in_memoria(("persone", tuple(rami)), calcola)


def voci_delle_persone(persone: list[Persona]) -> dict[str, str]:
    """uri -> chiave della voce (gruppo o componente) dei parlamentari in carica. I senatori sono in classifica nel loro
    gruppo del Senato: la chiave porta il ramo («senato:Lega»)."""
    out = {}
    for p in persone:
        if p.gruppo is None:
            continue
        k = p.voce.key if p.voce else "Misto"
        out[p.uri] = k if p.ramo in (None, "camera") else f"{p.ramo}:{k}"
    return out


# ---------- persone nominate nella risposta ----------

MIN_COGNOME = 4
_GRUPPO_DOPO = re.compile(r"\s*\(([^()]{1,60})\)")
_SPEZZA_NOME = re.compile(r"[\s\-–—]+")
_NOMI_GRUPPI: list[re.Pattern] | None = None


def _maschera_gruppi(piegato: str) -> str:
    """La risposta piegata con i nomi dei gruppi in bianco, stessa lunghezza: «Lega - Salvini Premier» e «Futuro
    Nazionale Vannacci» non nominano Salvini né Vannacci."""
    global _NOMI_GRUPPI
    if _NOMI_GRUPPI is None:
        nomi = {n for v in VOCI if v.kind != "government" for n in [v.label, *v.names]} | {"Lega Salvini Premier", "Salvini Premier"}
        _NOMI_GRUPPI = []
        for n in sorted(nomi, key=len, reverse=True):
            parole = [w for w in _SPEZZA_NOME.split(_piega_uguale(re.sub(r"\([^)]*\)", " ", n))) if w]
            if len(parole) >= 2:
                _NOMI_GRUPPI.append(re.compile(r"(?<![\w])" + r"[\s\-–—]+".join(map(re.escape, parole)) + r"(?![\w])"))
    for rx in _NOMI_GRUPPI:
        piegato = rx.sub(lambda m: " " * len(m.group(0)), piegato)
    return piegato


def _maschera_citazioni(piegato: str) -> str:
    """Un nome dentro una citazione è una parola di chi parla («al collega Coin direi…»), non una voce della risposta."""
    return re.sub(r"«[^«»]*»", lambda m: "«" + " " * (len(m.group(0)) - 2) + "»", piegato)


def _occorrenze(piegato: str, ago: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"(?<![\w'])" + re.escape(ago) + r"(?![\w])", piegato)]


# un cognome da solo non è una persona quando fa da nome di battesimo («Graziano Delrio», «Bruno Tabacci»: subito dopo
# un'altra parola con la maiuscola) o da nome comune («il Piano nazionale», «dal Piano»: dopo un articolo maschile o una
# preposizione articolata, che davanti a un cognome non si usano)
_NOME_DOPO = re.compile(r"[ \t]+[A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'’]{2,}")
_ARTICOLO_PRIMA = re.compile(r"(?:^|[\s(«\"])(?:il|lo|un|uno|del|dello|dal|dallo|al|allo|nel|nello|sul|sullo|col)\s+$", re.I)
# né il nome di un atto: «mozioni Quartini ed altri n. 1-00369, Richetti ed altri n. 1-00388» nominano mozioni, non voci
_ED_ALTRI = re.compile(r"\s+e(?:d)?\s+altri\b", re.I)


def _da_cognome(testo: str, a: int, b: int) -> bool:
    """Se la parola in testo[a:b] può essere un cognome usato da solo."""
    return not (_NOME_DOPO.match(testo, b) or _ARTICOLO_PRIMA.search(testo[max(0, a - 12):a]) or _ED_ALTRI.match(testo, b))


def persone_nominate(risposta: str, persone: list[Persona]) -> list[dict]:
    """Le persone in carica nominate nella risposta. Il nome intero conta sempre. Il cognome da solo conta se è scritto
    con la maiuscola, non fa da nome di battesimo né da nome comune (_da_cognome), e o è di una persona sola, o un
    gruppo tra parentesi subito dopo («Rossi (FdI)») distingue gli omonimi. Il gruppo scritto tra parentesi si confronta
    con quello vero."""
    testo = _APOSTROFI.sub("'", risposta)
    piegato = _maschera_citazioni(_maschera_gruppi(_piega_uguale(testo)))
    per_cognome: dict[str, list[Persona]] = {}
    for p in persone:
        if p.family:
            per_cognome.setdefault(_piega_uguale(p.family), []).append(p)

    def gruppo_scritto(fine: int) -> tuple[str | None, Voce | None]:
        m = _GRUPPO_DOPO.match(testo, fine)
        if not m:
            return None, None
        dentro = m.group(1)
        return dentro.strip(), next((v for v in VOCI if nominata_come(dentro, v)), None)

    trovate: dict[str, dict] = {}

    def aggiungi(p: Persona, scritto: str, fine: int, come: str) -> None:
        if p.uri in trovate:
            return
        gs, gv = gruppo_scritto(fine)
        v = p.voce
        trovate[p.uri] = {"person_id": p.uri, "uri": p.uri, "name": p.nome,
                          "group": v.label if v else etichetta_gruppo(p.gruppo, p.componente), "voice": v.key if v else None,
                          "in_government": p.al_governo, "named_as": scritto, "matched_by": come, "group_written": gs,
                          "group_mismatch": bool(gv and v and gv.key != v.key and not (gv.kind == "government" and p.al_governo))}

    for p in persone:
        for a, b in _occorrenze(piegato, _piega_uguale(p.nome)):
            aggiungi(p, testo[a:b], b, "full_name")
            break
    for cognome, omonimi in per_cognome.items():
        if len(cognome) < MIN_COGNOME:
            continue
        for a, b in _occorrenze(piegato, cognome):
            if not testo[a].isupper() or not _da_cognome(testo, a, b):
                continue
            if len(omonimi) == 1:
                aggiungi(omonimi[0], testo[a:b], b, "surname")
                break
            _, gv = gruppo_scritto(b)
            scelti = [p for p in omonimi if gv and p.voce and p.voce.key == gv.key]
            if len(scelti) == 1:
                aggiungi(scelti[0], testo[a:b], b, "surname_and_group")
                break
    return list(trovate.values())


# ---------- citazioni ----------

SQL_INTERVENTI_CITATI = """
SELECT s.uri, s.person, s.as_office, s.as_group, st.kind AS sitting_kind, st.date, st.chamber, i.title AS debate,
       p.given_name, p.family_name,
       g.kind, g.name AS g_name, pg.name AS misto
FROM speech s JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
LEFT JOIN person p ON p.uri = s.person
LEFT JOIN grp g ON g.uri = group_at(s.person, st.date) LEFT JOIN grp pg ON pg.uri = g.part_of
WHERE s.uri = ANY(%s)"""


def _al_governo_il(pr: A.Profili, uri: str | None, il: dt.date, senza_gruppo: bool = False) -> bool:
    """Parla per il Governo anche senza la qualifica scritta: al governo quel giorno e senza seggio, oppure (come nel
    recupero, recupero_canali.SQL_INTERVENTI) al governo quel giorno e senza gruppo dichiarato nell'Aula della Camera,
    dove il resoconto non scrive la carica dei ministri che sono anche parlamentari."""
    p = pr.persone.get(pr.alias.get(uri or "", uri or ""))
    return bool(p and (not p["mandati"] or senza_gruppo) and any(A.attivo(g["start"], g["end"], il) for g in p["governo"]))


def controlla_citazioni(c: psycopg.Connection, risposta: str, pr: A.Profili) -> tuple[list[dict], list[str]]:
    """Le citazioni con l'esito (exact, omissions, not_found) e, se trovate, l'intervento con chi parla, la sua voce alla
    data e se è nominato vicino. Le citazioni troppo corte per verificarle vanno a parte."""
    from ..strumenti.comune import url_interventi

    v = citazioni.verifica(c, risposta)
    trovati = [e["speech"] for e in v["results"] if e.get("found")]
    link = url_interventi(c, trovati)
    righe = {r["uri"]: r for r in c.execute(SQL_INTERVENTI_CITATI, (trovati,))} if trovati else {}
    out, corte, da = [], [], 0
    for e in v["results"]:
        q = e["quote"]
        inizio = risposta.find(q, da)
        inizio = inizio if inizio >= 0 else risposta.find(q)
        fine = inizio + len(q)
        da = max(da, fine)
        if not e["found"] and e.get("reason") == "troppo corta per verificarla":
            corte.append(q)
            continue
        x = {"text": q, "start": inizio, "end": fine, "status": "not_found"}
        r = righe.get(e.get("speech"))
        if e["found"] and r:
            componente = r["g_name"] if r["kind"] == "misto_component" else None
            gruppo = r["misto"] if componente else r["g_name"]
            governo = ruolo_nel_dibattito(r["as_office"], _al_governo_il(
                pr, r["person"], r["date"], r["as_group"] is None and r["sitting_kind"] == "assembly_verbatim")) == "governo"
            voce = voce_del_gruppo(gruppo, componente, governo)
            cognome = nome_camera(r["family_name"])
            x.update(status="omissions" if citazioni.PARTI.search(q) else "exact",
                     attributed=nominato_vicino(risposta, inizio, fine, cognome),
                     speech={"speech_id": r["uri"], "person_id": pr.alias.get(r["person"], r["person"]), "uri": r["person"],
                             "name": f"{nome_camera(r['given_name'])} {cognome}".strip() or e.get("speaker"),
                             "group": voce.label if voce else etichetta_gruppo(gruppo, componente),
                             "voice": voce.key if voce else None, "speaking_role": r["as_office"], "date": str(r["date"]),
                             "debate": r["debate"], "chamber": r["chamber"], "url": link.get(r["uri"])})
        elif e.get("reason"):
            x["reason"] = e["reason"]
        out.append(x)
    return out, corte


# ---------- chi ha parlato del tema ----------

def _voci_dei_gruppi(pr: A.Profili, rami: list[str]) -> dict[str, list[str]]:
    """chiave della voce -> uri dei gruppi (o componenti) che parlano per lei nei rami; «Misto» per il Misto stesso."""
    out: dict[str, list[str]] = {}
    for u, g in pr.gruppi.items():
        if g["chamber"] not in rami:
            continue
        comp = g["kind"] == "misto_component"
        v = voce_del_gruppo(None if comp else g["name"], g["name"] if comp else None, False)
        out.setdefault(v.key if v else "Misto", []).append(u)
    return out


SQL_PERIMETRO = """
SELECT x.*, group_at(x.person, x.date) AS grp FROM (
  SELECT s.person, s.uri AS item, st.date, st.chamber, s.as_office, 1 - (v.embedding <=> %(q)s::halfvec(1024)) AS score
  FROM speech s JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
  JOIN passage p ON p.source = 'speech' AND p.uri = s.uri JOIN speech_vector v ON v.hash = p.hash AND v.model = %(m)s
  WHERE s.person IN (SELECT person FROM membership WHERE grp = ANY(%(grp)s)) AND st.kind = 'assembly_verbatim'
    AND st.chamber = ANY(%(rami)s) AND group_at(s.person, st.date) = ANY(%(grp)s)
  ORDER BY v.embedding <=> %(q)s::halfvec(1024) LIMIT %(k)s) x
WHERE x.score >= %(soglia)s"""


_pool: OrderedDict[tuple, dict] = OrderedDict()


def chi_ha_parlato(c: psycopg.Connection, q: str, rami: list[str], pr: A.Profili) -> dict[str, str | None]:
    """uri -> voce per cui ha parlato del tema (con il ramo per il Senato), None per gli oratori dei primi brani (contano
    nella voce di oggi). Un brano conta per il gruppo di chi parla alla data dell'intervento: gli interventi di Marattin
    in Italia Viva contano per Italia Viva, non per il Misto. Chi parla per il Governo non entra. In memoria per
    vettore e rami."""
    chiave = (q, tuple(rami))
    if chiave not in _pool:
        A._ricorda(_pool, chiave, _chi_ha_parlato(c, q, rami, pr))
    return _pool[chiave]


def _chi_ha_parlato(c: psycopg.Connection, q: str, rami: list[str], pr: A.Profili) -> dict[str, str | None]:
    righe = []
    for ramo in rami:
        righe += A.evidenze(c, q, [ramo]).interventi
    voci = _voci_dei_gruppi(pr, rami)
    di_voce = {g: k for k, gs in voci.items() for g in gs}

    def chiave(r: dict) -> str | None:
        k = di_voce.get(r["grp"] or "")
        return None if k is None else (k if r["chamber"] == "camera" else f"{r['chamber']}:{k}")

    righe = [r for r in righe if not GOVERNO_RE.match(r["as_office"] or "")]
    righe.sort(key=lambda r: -r["score"])
    pool: dict[str, str | None] = {pr.alias.get(r["person"], r["person"]): None for r in righe[:PRIMI_VICINI]}
    per_voce: dict[str, list[dict]] = {}
    for r in righe:
        k = di_voce.get(r["grp"] or "")
        if k and r["score"] >= SOGLIA_PERIMETRO and len(per_voce.setdefault(k, [])) < PER_GRUPPO:
            per_voce[k].append(r)
    # le voci con meno di PER_GRUPPO brani fra i vicini: la ricerca sui soli loro membri
    mancano = [k for k in voci if len(per_voce.get(k, [])) < PER_GRUPPO]
    if mancano:
        A._prepara(c, A.con_indice(c))
        c.execute("SET enable_nestloop = on")
        try:
            for k in mancano:
                try:
                    per_voce[k] = [r for r in c.execute(SQL_PERIMETRO, {"q": q, "m": modello.MODELLO_VETTORI, "grp": voci[k],
                                                                         "rami": rami, "k": PER_GRUPPO, "soglia": SOGLIA_PERIMETRO})
                                   if not GOVERNO_RE.match(r["as_office"] or "")]
                except psycopg.Error as e:
                    log.warning("perimetro della voce %s non disponibile: %s", k, type(e).__name__)
        finally:
            A._ripristina(c)
    for rs in per_voce.values():
        for r in rs:
            u = pr.alias.get(r["person"], r["person"])
            if pool.get(u) is None:
                pool[u] = chiave(r)
    return pool


def voci_sul_tema(pool: dict[str, str | None], voce_di: dict[str, str]) -> set[str]:
    """Le voci con almeno uno che ha parlato del tema (la voce alla data, se no quella di oggi), senza il ramo."""
    out = set()
    for u, alla_data in pool.items():
        k = alla_data or voce_di.get(u)
        if k:
            out.add(k.split(":", 1)[-1])
    return out


def posizioni(classifica: list[dict], voce_di: dict[str, str], pool: dict[str, str | None] | None) -> dict[str, dict]:
    """uri -> posizione nella sua voce (da 1), quanti nella voce, punteggio. Solo chi è in carica, ognuno nella sua voce
    (una componente del Misto per conto suo); con `pool`, solo chi ha parlato del tema."""
    gruppi: dict[str, dict[str, float]] = {}
    for d in classifica:
        u = d["uri"]
        if pool is not None and u not in pool:
            continue
        alla_data = pool.get(u) if pool else None
        if alla_data:
            gruppi.setdefault(alla_data, {})[u] = d["punteggio"]
        elif u in voce_di:
            gruppi.setdefault(voce_di[u], {})[u] = d["punteggio"]
    out = {}
    for g, membri in gruppi.items():
        for i, (u, s) in enumerate(sorted(membri.items(), key=lambda kv: -kv[1]), 1):
            out[u] = {"rank": i, "pool_size": len(membri), "group_size": len(membri), "score": s, "ranking_group": g}
    return out


def posizione_voce(x: dict, tabella: dict | None, fonte: str = "quoted", pool: str = POOL_SUL_TEMA) -> dict:
    """Perché una persona citata o nominata è, o non è, una voce autorevole."""
    ruolo = "governo" if x["voice"] == "Governo" or x.get("in_government") else ruolo_nel_dibattito(x.get("speaking_role"), False)
    e = {"person_id": x["person_id"], "uri": x.get("uri", x["person_id"]), "name": x["name"], "group": x["group"],
         "voice": x["voice"], "role": ruolo, "source": fonte}
    pos = (tabella or {}).get(x["person_id"])
    if tabella is not None:
        e["pool"] = pool
    if pos:
        e.update(rank=pos["rank"], pool_size=pos["pool_size"], group_size=pos["pool_size"])
    elif tabella is not None and pool == POOL_SUL_TEMA:
        e["on_topic"] = False                       # non ha parlato del tema: non può esserne una voce autorevole
    if ruolo in ("governo", "relatore"):
        e["authoritative"] = True
    elif pos:
        e["authoritative"] = pos["rank"] <= AUTOREVOLI_PRIMI
    else:
        e["authoritative"] = None if tabella is None else False
    return e


# ---------- il rapporto ----------

def tema_dalla_risposta(risposta: str, massimo: int = TEMA_DALLA_RISPOSTA) -> str:
    """Le prime frasi della risposta senza le citazioni, fino a `massimo` caratteri."""
    testo = " ".join(_APOSTROFI.sub("'", _CITAZIONE.sub(" ", risposta)).split())
    out = ""
    for frase in re.split(r"(?<=[.!?])\s+", testo):
        if out and len(out) + len(frase) + 1 > massimo:
            break
        out = f"{out} {frase}".strip()
    return out[:massimo]


def rapporto(risposta: str, citate: list[dict], corte: list[str], voci: list[Voce], classifica: list[dict] | None,
             tema: str, fonte_tema: str, nominate: list[dict], voce_di: dict[str, str], rami: list[str],
             pool: dict[str, str | None] | None, fonte_ambito: str | None = None) -> dict:
    """Il rapporto nella forma della vecchia /api/verify. `pool`: chi ha parlato del tema; None mette in classifica
    tutti i membri in carica (POOL_GRUPPO, la regola di prima del 16/10, per gli usi fuori linea)."""
    esatte = [q for q in citate if q.get("status") == "exact"]
    if pool is not None:
        pool = dict(pool)
        for q in esatte:                             # chi è citato esattamente ha parlato del tema per definizione
            pool.setdefault(q["speech"]["person_id"], None)
    tipo_pool = POOL_GRUPPO if pool is None and classifica else POOL_SUL_TEMA

    parlato = voci_sul_tema(pool, voce_di) if pool is not None else None
    gruppi = []
    for v in voci:
        citata_da = sorted({q["speech"]["name"] for q in esatte if q["speech"]["voice"] == v.key and q.get("attributed")})
        come = nominata_come(risposta, v) or next((p["name"] for p in nominate if p["voice"] == v.key), None)
        if citata_da:
            stato = "quoted"
        elif parlato is not None and v.kind != "government" and v.key not in parlato:
            stato = "silent"                         # nessuno della voce ha parlato del tema: un dato, non un buco
        else:
            stato = "named" if come else "missing"
        gruppi.append({"key": v.key, "label": v.label, "kind": v.kind, "status": stato, "named_as": come, "quoted_by": citata_da})
    mancanti = [g for g in gruppi if g["status"] == "missing"]
    mute = [g for g in gruppi if g["status"] == "silent"]

    tabella = posizioni(classifica, voce_di, pool) if classifica is not None else None
    voci_out, visti = [], set()
    for q in esatte:
        if q["speech"]["person_id"] not in visti:
            visti.add(q["speech"]["person_id"])
            voci_out.append(posizione_voce(q["speech"], tabella, pool=tipo_pool))
    for p in nominate:
        if p["person_id"] not in visti:
            visti.add(p["person_id"])
            voci_out.append(posizione_voce(p, tabella, "named", tipo_pool))
    if not voci_out:
        esito_aut = "na"
    elif any(v["authoritative"] is False for v in voci_out):
        esito_aut = "fail"
    elif any(v["authoritative"] is None for v in voci_out):
        esito_aut = "na"
    else:
        esito_aut = "pass"

    sbagliate = [q for q in citate if q.get("status") in ("modified", "omissions")]
    non_attribuite = [q for q in esatte if not q.get("attributed")]
    if not citate:
        esito_cit = "na"
    elif sbagliate or non_attribuite or any(q["status"] == "not_found" for q in citate):
        esito_cit = "fail"
    else:
        esito_cit = "pass"

    out = {
        "scope": ETICHETTE_AMBITO.get(tuple(r for r in RAMI if r in rami), ETICHETTE_AMBITO[("camera",)]),
        "rules": {"min_quote_words": 3, "authority_top_n": AUTOREVOLI_PRIMI, "authority_pool": tipo_pool},
        "summary": {"groups": "fail" if mancanti else "warn" if mute else "pass", "authority": esito_aut, "quotes": esito_cit},
        # named: le voci presenti (citate o nominate); le mute no
        "groups": {"items": gruppi, "named": len(gruppi) - len(mancanti) - len(mute), "silent": len(mute), "total": len(gruppi),
                   "mismatches": [p for p in nominate if p["group_mismatch"]]},
        "people": nominate,
        "authority": {"topic": tema, "topic_source": fonte_tema, "available": classifica is not None, "pool": tipo_pool,
                      "voices": voci_out},
        "quotes": {"items": citate, "exact": len(esatte), "total": len(citate), "short": corte},
    }
    if fonte_ambito:
        out["scope_chambers"] = [r for r in RAMI if r in rami]
        out["scope_source"] = fonte_ambito
    return out


@dataclass
class _Ramo:
    rami: tuple
    da: dt.date | None = None
    a: dt.date | None = None


def verifica(c: psycopg.Connection, risposta: str, domanda: str | None, rami: list[str], ip: str | None = None) -> dict:
    """Le tre garanzie su una risposta, nella forma della vecchia /api/verify: {scope, rules, summary{groups, authority,
    quotes}, groups{items, named, silent, total, mismatches}, people, authority{topic, available, voices}, quotes{items,
    exact, total, short}, scope_chambers, scope_source, computation_time_ms}. Se il vettore della domanda o la ricerca
    degli interventi non riescono, l'autorevolezza non è disponibile e i gruppi si controllano senza le voci mute."""
    t0 = time.perf_counter()
    rami = [r for r in RAMI if r in (rami or RAMI)] or list(RAMI)
    if domanda and len(domanda.strip()) >= 2:
        tema, fonte_tema = domanda.strip()[:500], "question"
    else:
        tema, fonte_tema = tema_dalla_risposta(risposta), "answer"
    pr = A.profili(c)
    citate, corte = controlla_citazioni(c, risposta, pr)
    attesi, fonte_ambito = rami_attesi(rami, domanda or "", risposta, citate)
    voci = voci_in_carica(c, attesi)
    persone = persone_in_carica(c, attesi, pr)
    nominate = persone_nominate(risposta, persone)

    classifica, pool = None, None
    if tema:
        try:
            q = A.vettore(tema, ip)
            # una classifica per ramo: i senatori stanno in classifica fra i senatori
            classifica = [d for r in attesi for d in A.punteggi(c, tema, _Ramo((r,)), ip=ip) if r in d["rami"] or not d["rami"]]
            if any("interventi" in d.get("degradato", ()) for d in classifica):
                classifica = None                   # senza i brani d'Aula non si sa chi ha parlato del tema
            else:
                pool = chi_ha_parlato(c, q, attesi, pr)
        except modello.ModelloNonDisponibile as e:
            log.warning("autorevolezza non disponibile per la verifica: %s", e)
            classifica = None
    out = rapporto(risposta, citate, corte, voci, classifica, tema, fonte_tema, nominate, voci_delle_persone(persone),
                   attesi, pool if classifica is not None else None, fonte_ambito)
    out["computation_time_ms"] = round((time.perf_counter() - t0) * 1000)
    log.info("verifica: %d citazioni (%d esatte), %d/%d voci, autorevolezza %s, %d ms", out["quotes"]["total"],
             out["quotes"]["exact"], out["groups"]["named"], out["groups"]["total"], out["summary"]["authority"],
             out["computation_time_ms"])
    return out
