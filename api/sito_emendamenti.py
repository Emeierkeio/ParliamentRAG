"""Emendamenti per il sito: l'elenco delle leggi con emendamenti e, per ogni legge, i testi articolo per articolo e comma
per comma, le fasi dell'iter, gli emendamenti con firmatari e gruppi, i voti in Aula e le modifiche fra un testo e il
successivo. Tutto dal Postgres v3, nel formato JSON che il lettore del sito (sito/js/emendamenti.js) legge già.

Una legge è l'insieme delle sue letture (C. 2822, S. 1971, C. 2822-B): il Senato le lega con lo stesso idDdl, la
Camera con le trasmissioni e con il titolo («S. 1689. - …»). L'idDdl è anche l'identificativo della legge negli indirizzi
del sito; una legge mai arrivata al Senato non ce l'ha e prende «camera-<numero>».

I risultati restano in memoria per qualche minuto: le leggi grandi (la legge di bilancio, 12 mila emendamenti) si
compongono in qualche secondo e i dati cambiano solo con il giro notturno."""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import re
import threading
import time
from collections import Counter, defaultdict
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from .db import per_richiesta
from .strumenti.comune import LEGISLATURA

router = APIRouter(include_in_schema=False)
Db = Annotated[psycopg.Connection, Depends(per_richiesta)]

DURATA = 600                                   # secondi in memoria
ELETTORALE = ("legge-elettorale", "55214")     # la legge elettorale ha un indirizzo suo nel sito
MAGGIORANZA = ["FdI", "Lega", "FI", "NM"]
ORDINALE = {1: "prima", 2: "seconda", 3: "terza", 4: "quarta", 5: "quinta"}
SEDE = {"assembly": "assemblea"}               # tutte le altre sedi (referente, legislativa, committee …) sono commissione


# ---------- memoria ----------

_memo: dict[str, tuple[float, object]] = {}
_blocco = threading.Lock()


def _in_memoria(chiave: str, calcola):
    with _blocco:
        x = _memo.get(chiave)
    if x and time.monotonic() - x[0] < DURATA:
        return x[1]
    valore = calcola()
    with _blocco:
        if len(_memo) > 60:                    # poche leggi aperte insieme: si butta tutto e si ricomincia
            _memo.clear()
        _memo[chiave] = (time.monotonic(), valore)
    return valore


# ---------- sigle dei gruppi, le stesse del sito (B.sigla in sito/js/base.js) ----------

REGOLE = [(r"FRATELLI", "FdI"), (r"PARTITO DEMOCRATICO", "PD"), (r"^LEGA", "Lega"), (r"FORZA ITALIA", "FI"),
          (r"MOVIMENTO 5", "M5S"), (r"ALLEANZA VERDI", "AVS"), (r"AZIONE", "Azione"), (r"ITALIA VIVA", "IV"),
          (r"NOI MODERATI|Civici", "NM"), (r"Autonomie", "Aut"), (r"\+Europa", "+Europa"), (r"Futuro Nazionale", "FNV"),
          (r"Minoranze", "MinLing"), (r"Sud chiama", "SCN"), (r"PSI", "PSI"), (r"Italia Domani", "ID-MR"),
          (r"Rifondazione Comunista", "PRC-SE-OS"), (r"MISTO", "Misto")]


def sigla(nome: str | None) -> str | None:
    """Il nome del gruppo o della componente del Misto → la sigla del sito. Il Misto resta per componente."""
    if not nome:
        return None
    for r, s in REGOLE:
        if re.search(r, nome, re.I):
            return s
    return "Misto"


# ---------- stato delle letture, nel vocabolario del Senato che il sito traduce ----------

STATI_CAMERA = [(r"definitivamente.*non ancora pubblicato", "appr. def. non pubbl"), (r"definitivamente", "appr. definit. Legge"),
                (r"esame in Commissione", "esame in comm."), (r"con modificazioni", "appr. con modificaz"),
                (r"testo unificato", "appr. in t.u."), (r"^Approvato", "approvato"), (r"Concluso l'esame", "concluso l'esame"),
                (r"In discussione", "all'esame assemblea"), (r"^Respinto", "respinto"), (r"^Ritirato", "ritirato"),
                (r"^Assorbito", "assorbito"), (r"Assegnato|Da assegnare", "assegnato")]


def stato(chamber: str, s: str | None) -> str | None:
    if not s or chamber == "senato":
        return s
    return next((v for r, v in STATI_CAMERA if re.search(r, s, re.I)), s)


def definitivo(s: str | None) -> bool:
    return bool(s) and s.startswith("appr. def")


# ---------- esiti degli emendamenti ----------

ESITI = [(r"^approvat|^accolt", "approvato"), (r"^respint", "respinto"), (r"inammissibil|improponibil", "inammissibile"),
         (r"^preclus|^assorbit", "precluso"), (r"^ritirat", "ritirato"), (r"improcedibil", "improcedibile"),
         (r"trasformat", "trasformato in odg"), (r"^v\. testo|^sost\. id|^id\. em", "vedi altro testo")]


def esito(raw: str | None) -> str | None:
    if not raw:
        return None
    low = raw.strip().lower()
    return next((v for r, v in ESITI if re.search(r, low)), "altro")


# ---------- testi: da act_article ad articoli, commi e blocchi ----------

COMMA_CAMERA = re.compile(r"^(\d+(?:-[a-z]+)?)\.\s+(.*)$", re.S)
COMMA_SENATO = re.compile(r"^\d+(?:-[a-z]+)?$")
LETTERA_CAMERA = re.compile(r"^([a-z]{1,2}(?:-[a-z]+)?)\)\s+(.*)$", re.S)
LETTERA_SENATO = re.compile(r"^[a-z]{1,2}(?:-[a-z]+)?\)?$")
NUM_ARTICOLO = re.compile(r"^(?:Art\.|Articolo)?\s*(\d+(?:\s*-\s*[a-z]+)?)\.?$", re.I)


def pulisci(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"(\d)-\s+(bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)\b", r"\1-\2", t)
    t = re.sub(r"\s+([,.;:)])", r"\1", t)
    return t.replace("« ", "«").replace(" »", "»")


def articolo(numero: str | None, testo: str) -> dict:
    """Un articolo come lo scrivono la Camera («Art. 1.», «1. Il comma…», «a) la lettera…») e il Senato (numero,
    rubrica, numero del comma e testo, lettera e testo, ognuno nel suo paragrafo)."""
    par = [pulisci(p) for p in re.split(r"\n\s*\n", testo or "") if p.strip()]
    num = (numero or "").strip()               # la colonna number a volte prende un numero citato nella rubrica: vince il testo
    if par and NUM_ARTICOLO.match(par[0]):
        num = re.sub(r"\s", "", NUM_ARTICOLO.match(par[0]).group(1))
        par = par[1:]
    rubrica = ""
    if par and par[0].startswith("("):
        pezzi = [par.pop(0)]                   # la rubrica può andare a capo: «(Agricoltore custode» «e del territorio)»
        while ")" not in pezzi[-1] and par:
            pezzi.append(par.pop(0))
        rubrica = " ".join(pezzi).strip("() ")
    commi: list[dict] = []
    virgolette, attesa = 0, None               # attesa: numero di comma o lettera del Senato, il testo è nel paragrafo dopo
    for p in par:
        fuori = virgolette == 0
        if fuori and COMMA_SENATO.match(p):
            attesa = ("comma", p)
            continue
        if fuori and LETTERA_SENATO.match(p) and commi:
            attesa = ("lettera", p.rstrip(")") + ")")
            continue
        m, l = COMMA_CAMERA.match(p), LETTERA_CAMERA.match(p)
        if attesa and attesa[0] == "comma":
            commi.append({"num": attesa[1], "blocks": [{"kind": "p", "text": p, "depth": 0}]})
        elif attesa and attesa[0] == "lettera":
            commi[-1]["blocks"].append({"kind": "point", "label": attesa[1], "text": p, "depth": 0})
        elif fuori and m:
            commi.append({"num": m.group(1), "blocks": [{"kind": "p", "text": m.group(2), "depth": 0}]})
        elif not commi:
            commi.append({"num": "1", "blocks": [{"kind": "p", "text": p, "depth": 0}]})
        elif fuori and l:
            commi[-1]["blocks"].append({"kind": "point", "label": l.group(1) + ")", "text": l.group(2), "depth": 0})
        else:
            commi[-1]["blocks"].append({"kind": "p", "text": p, "depth": 0 if fuori else 1})
        attesa = None
        virgolette = max(0, virgolette + p.count("«") - p.count("»"))
    return {"num": num, "heading": rubrica, "commi": commi}


def articoli_decreto(arts: list[dict]) -> list[dict]:
    """Un disegno di legge di conversione ha il suo articolo 1 e poi quelli del decreto: si tengono quelli del decreto."""
    inizi = [i for i, a in enumerate(arts) if a["num"] == "1"]
    return arts[inizi[-1]:] if len(inizi) > 1 else arts


def misura(arts: list[dict] | None) -> int:
    return sum(len(a["commi"]) for a in arts or [])


# ---------- confronto fra testi ----------

def testo_comma(c: dict) -> str:
    return " ".join((b.get("label", "") + " " + b["text"]).strip() for b in c["blocks"])


def chiave_parola(w: str) -> str:
    """Camera e Senato punteggiano lo stesso testo in modo diverso: la punteggiatura non conta."""
    return re.sub(r"[«»\"'.,;:()\s–-]", "", w).lower()


def impronta(testo: str | None) -> str:
    """Il testo senza punteggiatura, spazi e «°»: «1° gennaio 2040.» e «1 gennaio 2040 .» sono lo stesso emendamento."""
    parole = [k for k in (chiave_parola(w).replace("°", "") for w in (testo or "").split()) if k]
    return hashlib.sha1(" ".join(parole).encode()).hexdigest()[:16]


def stesso_testo(a: str, b: str) -> bool:
    return [k for k in map(chiave_parola, a.split(" ")) if k] == [k for k in map(chiave_parola, b.split(" ")) if k]


def differenze(vecchio: str, nuovo: str) -> list[list]:
    a, b = vecchio.split(" "), nuovo.split(" ")
    ops: list[list] = []
    sm = difflib.SequenceMatcher(a=[chiave_parola(w) for w in a], b=[chiave_parola(w) for w in b], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            ops.append(["eq", " ".join(b[j1:j2])])
            continue
        if tag in ("delete", "replace"):
            ops.append(["del", " ".join(a[i1:i2])])
        if tag in ("insert", "replace"):
            ops.append(["ins", " ".join(b[j1:j2])])
    return ops


def modifiche(vecchio: list[dict], nuovo: list[dict], approvati: list[dict]) -> list[dict]:
    """I commi cambiati fra due testi, ognuno con gli emendamenti approvati che lo spiegano (lo citano o ne contengono
    il testo inserito)."""
    prima = {(a["num"], c["num"]): testo_comma(c) for a in vecchio for c in a["commi"]}
    fuori = []
    for art in nuovo:
        for c in art["commi"]:
            ora, era = testo_comma(c), prima.get((art["num"], c["num"]))
            if era is not None and stesso_testo(era, ora):
                continue
            fonti = []
            for am in approvati:
                if am["article"] != art["num"]:
                    continue
                inseriti = [pulisci(q) for q in re.findall(r"«([^»]{6,})»", am["text"] or "")]
                if am["comma"] == c["num"] or any(q[:60] in ora for q in inseriti):
                    fonti.append(am["id"])
            fuori.append({"article": art["num"], "comma": c["num"], "kind": "nuovo" if era is None else "modificato",
                          "diff": differenze(era, ora) if era else [["ins", ora]], "amendments": fonti})
    return fuori


# ---------- dove tocca un emendamento ----------

RE_COMMA = re.compile(r"\bcomm[ai]\s+(\d+(?:-[a-z]+)?)", re.I)
RE_LETTERA = re.compile(r"\blettera\s+([a-z]{1,2}(?:-[a-z]+)?)\)", re.I)


def ancora(testo: str | None) -> tuple[str | None, str | None]:
    testa = (testo or "")[:160]
    if re.match(r"\s*sopprimerlo|\s*sostituirlo|\s*sostituire l'articolo", testa, re.I):
        return None, None
    c, l = RE_COMMA.search(testa), RE_LETTERA.search(testa)
    return (c.group(1) if c else None, l.group(1).lower() if l else None)


def titolo_breve(t: str) -> str:
    """Il titolo per la testata: prima l'oggetto, poi il numero del decreto."""
    x = re.sub(r'"?\s*<(?:em|i)>\s*\(approvat.*$', "", t or "", flags=re.S)
    x = re.sub(r"<[^>]+>", "", x)
    x = re.sub(r'^[^"“]*?[A-ZÀ-Ü]{3,}[^"“]*?:\s*["“]', "", x)
    x = re.sub(r"[\"“”]", "", x)
    x = re.sub(r"^[SC]\.\s*\d+(?:-[A-Z])?\.\s*-\s*", "", x)
    x = re.sub(r"^DISEGNO DI LEGGE COSTITUZIONALE:\s*", "", x, flags=re.I)
    x = re.sub(r"\s*\(\d+(?:-[A-Z])?\)\s*$", "", x).strip(" .")
    dl = re.match(r"Conversione in legge(?:, con modificazioni,)? del decreto-legge (\d+ \w+ (\d{4})), n\. (\d+), recante (.*)$", x, re.S)
    if dl:
        x = f"{dl.group(4).strip()} (decreto-legge {dl.group(3)}/{dl.group(2)})"
    return x[0].upper() + x[1:] if x else (t or "")


def compatta(d) -> str | None:
    return str(d).replace("-", "")[:8] if d else None


def sigla_atto(a: dict) -> str:
    return ("C." if a["chamber"] == "camera" else "S.") + a["number"]


# ---------- leggi: le letture legate fra loro ----------

def _leggi(c: psycopg.Connection) -> dict[str, list[dict]]:
    """slug → letture in ordine di data, solo per le leggi con almeno un emendamento."""
    def calcola():
        atti = c.execute("""SELECT uri, chamber, number, title, date, status, card_url FROM act
                            WHERE legislature = %s AND kind = 'bill'""", (LEGISLATURA,)).fetchall()
        per_uri = {a["uri"]: a for a in atti}
        senato = {a["number"]: a["uri"] for a in atti if a["chamber"] == "senato"}
        padre = {u: u for u in per_uri}

        def radice(u):
            while padre[u] != u:
                padre[u] = padre[padre[u]]
                u = padre[u]
            return u

        def unisci(a, b):
            if a in padre and b in padre:
                padre[radice(a)] = radice(b)

        primo_ddl: dict[str, str] = {}
        for a in atti:
            m = re.search(r"Ddliter/(\d+)", a["card_url"] or "")
            if a["chamber"] == "senato" and m:
                unisci(a["uri"], primo_ddl.setdefault(m.group(1), a["uri"]))
            t = re.match(r"\s*S\.\s*(\d+(?:-[A-Z]+)?)\.", a["title"] or "")
            if a["chamber"] == "camera" and t and t.group(1) in senato:
                unisci(a["uri"], senato[t.group(1)])
        for r in c.execute("SELECT act, other_ref FROM act_transmission"):
            n = re.match(r"S\.\s*(\d+(?:-[A-Z]+)?)$", r["other_ref"] or "")
            if n and n.group(1) in senato:
                unisci(r["act"], senato[n.group(1)])
        con_emendamenti = {r["act"]: r for r in c.execute(
            "SELECT act, count(*) AS n, max(coalesce(presented, sitting_date)) AS ultimo FROM amendment GROUP BY act")}
        gruppi: dict[str, list[dict]] = defaultdict(list)
        for u in per_uri:
            gruppi[radice(u)].append(per_uri[u])
        fuori: dict[str, list[dict]] = {}
        for letture in gruppi.values():
            if not any(a["uri"] in con_emendamenti for a in letture):
                continue
            letture.sort(key=lambda a: (a["date"] or dt.date.max, a["chamber"] != "camera", a["number"]))
            ddl = next((m.group(1) for a in letture if a["chamber"] == "senato"
                        for m in [re.search(r"Ddliter/(\d+)", a["card_url"] or "")] if m), None)
            slug = ddl or f"camera-{letture[0]['number']}"
            for a in letture:
                e = con_emendamenti.get(a["uri"])
                a["n"], a["ultimo"] = (e["n"], e["ultimo"]) if e else (0, None)
            fuori[slug] = letture
        return fuori
    return _in_memoria("leggi", calcola)


def _slug_esterno(slug: str) -> str:
    return ELETTORALE[0] if slug == ELETTORALE[1] else slug


# ---------- elenco ----------

def _commissioni(c: psycopg.Connection, atti: list[str]) -> dict[str, dict]:
    """La commissione di merito della prima lettura: la prima assegnata."""
    fuori = {}
    for r in c.execute("""SELECT DISTINCT ON (x.act) x.act, a.chamber, b.name FROM act_assignment x
                          JOIN act a ON a.uri = x.act JOIN body b ON b.uri = x.body
                          WHERE x.act = ANY(%s) AND coalesce(x.seat, 'referente') IN ('referente', 'redigente', 'deliberante')
                          ORDER BY x.act, x.date, x.body""", (atti,)):
        nome, materia = commissione(r["name"], r["chamber"])
        fuori[r["act"]] = {"ramo": "C" if r["chamber"] == "camera" else "S", "nome": nome, "materia": materia}
    return fuori


# Le commissioni permanenti della XIX: la Camera nei dati aperti dà solo il numero
MATERIE_CAMERA = {
    "I": "Affari costituzionali, della Presidenza del Consiglio e interni", "II": "Giustizia", "III": "Affari esteri e comunitari",
    "IV": "Difesa", "V": "Bilancio, tesoro e programmazione", "VI": "Finanze", "VII": "Cultura, scienza e istruzione",
    "VIII": "Ambiente, territorio e lavori pubblici", "IX": "Trasporti, poste e telecomunicazioni", "X": "Attività produttive, commercio e turismo",
    "XI": "Lavoro pubblico e privato", "XII": "Affari sociali", "XIII": "Agricoltura", "XIV": "Politiche dell'Unione europea"}


def commissione(nome: str, ramo: str) -> tuple[str, str]:
    """«VIII Commissione» → («VIII Commissione», «Ambiente, territorio e lavori pubblici»); «5ª Commissione permanente
    (Bilancio)» → («5ª Commissione», «Bilancio»)."""
    if re.match(r"^\s*COMMISSIONE SPECIALE", nome, re.I):
        return "Commissione speciale", ""
    m = re.match(r"^\s*([IVXL]+|\d+ª?)\s+COMMISSIONE(?:\s+PERMANENTE)?\s*(?:\((.+)\))?\s*$", nome, re.I)
    if not m:
        return nome.strip(), ""
    materia = re.sub(r"\s+", " ", m.group(2) or "").strip()
    if materia:
        materia = materia[0].upper() + materia[1:].lower() if materia.isupper() else materia
    elif ramo == "camera":
        materia = MATERIE_CAMERA.get(m.group(1).upper(), "")
    return f"{m.group(1)} Commissione", materia


def _voti_finali(c: psycopg.Connection, atti: list[str]) -> dict[str, list[dict]]:
    fuori: dict[str, list[dict]] = defaultdict(list)
    for r in c.execute("""SELECT x.act, v.uri, v.chamber, v.date, v.sitting, v.description, v.title, v.approved, v.favor, v.against,
                                 v.abstain, v.secret, v.source_url
                          FROM vote_act x JOIN vote v ON v.uri = x.vote WHERE x.act = ANY(%s) AND v.final ORDER BY v.date, v.number""", (atti,)):
        fuori[r["act"]].append(r)
    return fuori


def _iter(letture: list[dict], prime: dict[tuple[str, str], str], finali: dict[str, list[dict]]) -> list[dict]:
    """Le tappe per la riga dell'elenco: presentazione o trasmissione, commissione e Aula alla data del primo
    emendamento, voto finale."""
    passi = []
    for n, a in enumerate(letture):
        ramo, atto = ("C" if a["chamber"] == "camera" else "S"), sigla_atto(a)
        passi.append({"c": ramo, "label": "Presentata" if n == 0 else "Trasmessa", "date": compatta(a["date"]), "atto": atto})
        for sede, nome in (("commissione", "Commissione"), ("assemblea", "Aula")):
            if (a["uri"], sede) in prime:
                passi.append({"c": ramo, "label": nome, "date": prime[(a["uri"], sede)], "atto": atto, "sede": sede})
        legge = a is letture[-1] and definitivo(stato(a["chamber"], a["status"]))
        for v in finali.get(a["uri"], [])[-1:]:
            if v["approved"]:
                passi.append({"c": ramo, "label": "Legge" if legge else "Approvata", "date": compatta(v["date"]), "atto": atto,
                              "voto": f"{v['favor']} sì, {v['against']} no"})
        if legge and not any(p["label"] == "Legge" for p in passi):
            passi.append({"c": ramo, "label": "Legge", "date": None, "atto": atto})
    return passi


@router.get("/dati/emendamenti/leggi/index.json")
def elenco(c: Db):
    def calcola():
        leggi = _leggi(c)
        atti = [a["uri"] for xs in leggi.values() for a in xs]
        prime = {(r["act"], SEDE.get(r["venue"], "commissione")): compatta(r["d"]) for r in c.execute(
            """SELECT act, venue, min(coalesce(presented, sitting_date)) AS d FROM amendment GROUP BY act, venue ORDER BY d DESC""")}
        comm = _commissioni(c, [xs[0]["uri"] for xs in leggi.values()])
        finali = _voti_finali(c, atti)
        righe = []
        for slug, xs in leggi.items():
            ultima = xs[-1]
            righe.append({"slug": _slug_esterno(slug), "title": titolo_breve(xs[0]["title"]),
                          "numbers": [sigla_atto(a).replace(".", ". ") for a in xs], "stato": stato(ultima["chamber"], ultima["status"]),
                          "amendments": sum(a["n"] for a in xs), "date": xs[0]["date"].isoformat() if xs[0]["date"] else None,
                          "ultimo": compatta(max((a["ultimo"] for a in xs if a["ultimo"]), default=None)),
                          "temi": [], "iter": _iter(xs, prime, finali), "commissione": comm.get(xs[0]["uri"])})
        return sorted(righe, key=lambda r: -r["amendments"])
    return JSONResponse(_in_memoria("indice", calcola))


# ---------- una legge ----------

def _testi(c: psycopg.Connection, letture: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """Per lettura: i testi esaminato («in»), della commissione («comm») e approvato («out»), il più completo per tipo.
    Senato: act_text.kind; Camera: gli stampati della scheda, «_A.» per il testo della commissione."""
    uri = [a["uri"] for a in letture]
    codici: dict[str, tuple[str, str]] = {}
    for r in c.execute("SELECT code, act, kind FROM act_text WHERE act = ANY(%s)", (uri,)):
        tipo = {"presented": "in", "committee": "comm", "message": "out"}.get(r["kind"])
        if tipo:
            codici[r["code"]] = (r["act"], tipo)
    for r in c.execute("SELECT act, uri FROM act_version WHERE act = ANY(%s) AND uri LIKE '%%:vta%%'", (uri,)):
        codice = r["uri"].split(":vta19_", 1)[-1]
        codici.setdefault(codice, (r["act"], "comm" if "_A." in codice else "in"))
    per_codice: dict[str, list[dict]] = defaultdict(list)
    for r in c.execute("SELECT code, number, text FROM act_article WHERE code = ANY(%s) ORDER BY code, ord", (list(codici),)):
        per_codice[r["code"]].append(articolo(r["number"], r["text"]))
    fuori: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    for codice, (atto, tipo) in codici.items():
        arts = articoli_decreto(per_codice.get(codice) or [])
        if len(arts) == 1 and "convertito in legge" in testo_comma(arts[0]["commi"][0] if arts[0]["commi"] else {"blocks": []}):
            continue                           # solo l'articolo di conversione: le modifiche stanno in un allegato
        if arts and misura(arts) > misura(fuori[atto].get(tipo)):
            fuori[atto][tipo] = arts
    return fuori


def _voti_aula(c: psycopg.Connection, numero: str) -> dict[str, dict]:
    """Voti dell'Aula della Camera sugli emendamenti di un progetto, per numero di emendamento. Le sedute recenti
    scrivono il progetto nel titolo («Votazione Emendamento 25.3 DDL n. 2673»); le più vecchie solo nel primo voto di
    una serie («PDL 2822-A E ABB - EM 1.1», poi «EM 1.3»), quindi il progetto si segue nell'ordine dei voti."""
    num = numero.split("-")[0]
    proprio = re.compile(rf"(?:DDL|PDL)\w*\s+(?:n\.\s*)?0*{num}(?!\d)")
    righe = c.execute("""SELECT v.uri, v.sitting, v.date, v.number, v.title, v.description, v.approved, v.favor, v.against, v.abstain, v.secret
                         FROM vote v WHERE v.chamber = 'camera' AND v.legislature = %(leg)s AND v.sitting IN (
                           SELECT sitting FROM vote WHERE chamber = 'camera' AND legislature = %(leg)s
                           AND (title LIKE %(n)s OR description LIKE %(n)s))
                         ORDER BY v.sitting, v.number""", {"leg": LEGISLATURA, "n": f"%{num}%"}).fetchall()
    voti, corrente = {}, None
    for r in righe:
        d, titolo = r["description"] or "", (r["title"] or "").strip()
        m = re.match(r"^((?:PDL|DDL)\w*\s+[\w-]+)", d)
        if m:
            corrente = m.group(1)
        if titolo != "Votazione":
            corrente = None
        if not (proprio.search(titolo) or (corrente and proprio.search(corrente))):
            continue
        if titolo.startswith("Votazione Emendamento"):
            numeri = re.findall(r"\b(\d+\.\d+(?:\.\d+)?(?:/\d+)?)\b", d.split(", da votare")[0])
        else:
            em = re.search(r"\bEM\s+([\d.]+(?:,\s*[\d.]+)*)", d)
            numeri = re.split(r",\s*", em.group(1)) if em else []
        seduta = int(re.search(r"sed(\d+)", r["sitting"]).group(1))
        for n in numeri:
            voti[n] = {"id": r["uri"], "session": seduta, "date": r["date"].isoformat(), "outcome": "approvato" if r["approved"] else "respinto",
                       "in_favor": r["favor"], "against": r["against"], "abstained": r["abstain"], "secret": bool(r["secret"]),
                       "url": f"https://www.camera.it/leg19/410?idSeduta={seduta:04d}&tipo=votazioni"}
    return voti


def _per_gruppo(c: psycopg.Connection, voto: str) -> list[dict]:
    conta: dict[str, Counter] = defaultdict(Counter)
    for r in c.execute("""SELECT g.name, b.result, count(*) AS n FROM ballot b JOIN vote v ON v.uri = b.vote
                          LEFT JOIN grp g ON g.uri = group_at(b.person, v.date)
                          WHERE b.vote = %s AND b.result IN ('favor', 'against', 'abstain') GROUP BY 1, 2""", (voto,)):
        conta[sigla(r["name"]) or "Misto"][r["result"]] += r["n"]
    return [{"group": g, "favor": x["favor"], "against": x["against"], "abstain": x["abstain"]}
            for g, x in sorted(conta.items(), key=lambda kv: -(kv[1]["favor"] + kv[1]["against"]))]


# chi presenta senza essere un parlamentare con un gruppo: il tipo di firmatario della fonte
ENTI = {"governo": "Governo", "relatore": "Relatore", "relatori": "Relatori", "commissione": "Commissione",
        "commissioni": "Commissioni"}


def _emendamenti(c: psycopg.Connection, letture: list[dict]) -> list[dict]:
    """Gli emendamenti delle letture, con i firmatari e il gruppo (la componente, nel Misto) alla data."""
    per_atto = {a["uri"]: a for a in letture}
    righe = c.execute("""SELECT uri, act, number, kind, article, venue, outcome, text, coalesce(presented, sitting_date) AS d
                         FROM amendment WHERE act = ANY(%s) ORDER BY act, venue, uri""", (list(per_atto),)).fetchall()
    firme: dict[str, list[dict]] = defaultdict(list)
    for f in c.execute("""SELECT s.amendment, s.first, s.kind_raw, nullif(trim(concat_ws(' ', p.given_name, p.family_name)), '') AS nome,
                                 nullif(trim(concat_ws(' ', s.given_raw, s.family_raw)), '') AS grezzo, g.name AS gruppo
                          FROM amendment e JOIN amendment_signer s ON s.amendment = e.uri
                          LEFT JOIN person p ON p.uri = s.person
                          LEFT JOIN grp g ON g.uri = group_at(s.person, coalesce(e.presented, e.sitting_date, current_date))
                          WHERE e.act = ANY(%s) ORDER BY s.amendment, s.ord""", (list(per_atto),)):
        ente = None if f["gruppo"] else ENTI.get((f["kind_raw"] or "").strip().lower())
        firme[f["amendment"]].append({"name": f["nome"] or (f["grezzo"] or "").title() or ente or "Non indicato",
                                      "group": ente or sigla(f["gruppo"]), "first": bool(f["first"])})
    fuori = []
    for r in righe:
        a = per_atto[r["act"]]
        sede = SEDE.get(r["venue"], "commissione")
        aggiuntivo = re.match(r"^\d+(?:-\w+)?\.0\.", r["number"]) or re.match(r"\s*Dopo l'articolo", r["text"] or "", re.I)
        fuori.append({"id": r["uri"], "stage": f"{sigla_atto(a)}-{sede}", "number": r["number"], "version": None,
                      "kind": r["kind"] or ("articoloAggiuntivo" if aggiuntivo else "emendamento"),
                      "article": r["article"] or (r["number"].split(".")[0] if "." in r["number"] else None),
                      "comma": None, "letter": None, "outcome": esito(r["outcome"]), "outcome_raw": r["outcome"],
                      "signers": firme.get(r["uri"], []), "text": r["text"], "vote": None,
                      # l'impronta del solo testo, per riconoscere gli emendamenti identici di gruppi diversi
                      "hash": impronta(r["text"]),
                      "source": None, "date": compatta(r["d"]), "parent": None})
    return fuori


def legge(c: psycopg.Connection, slug: str) -> dict | None:
    letture = _leggi(c).get(slug)
    if not letture:
        return None
    testi = _testi(c, letture)
    emendamenti = _emendamenti(c, letture)
    per_tappa = Counter(a["stage"] for a in emendamenti)
    versioni, tappe, passi, eventi, per_versione = [], [], [], [], {}
    visti = {"C": 0, "S": 0}

    def versione(vid, etichetta, data, arts, fonte):
        if not arts:
            return None
        per_versione[vid] = arts
        versioni.append({"id": vid, "label": etichetta, "date": data, "source": fonte, "articles": arts})
        return vid

    ultima_uscita = None
    for a in letture:
        atto, ramo = sigla_atto(a), ("C" if a["chamber"] == "camera" else "S")
        visti[ramo] += 1
        casa = "Camera" if ramo == "C" else "Senato"
        lettura = ORDINALE.get(sum(visti.values()), "")
        fonte = (f"https://www.camera.it/leg19/126?leg=19&idDocumento={a['number']}" if ramo == "C" else a["card_url"])
        data = a["date"].isoformat() if a["date"] else None
        eventi.append({"date": data, "chamber": ramo, "label": f"Presentata {'alla Camera' if ramo == 'C' else 'al Senato'}",
                       "detail": atto.replace(".", ". "), "url": fonte, "stage": None})
        t = testi.get(a["uri"], {})
        entrata = versione(f"{atto}-in", f"{casa}, testo esaminato", data, t.get("in"), fonte) or ultima_uscita
        comm = versione(f"{atto}-comm", f"{casa}, testo della commissione", None, t.get("comm"), fonte)
        uscita = versione(f"{atto}-out", f"Approvato dal {casa}", None, t.get("out"), fonte)
        for sede, testo in (("commissione", entrata), ("assemblea", comm or entrata)):
            tid = f"{atto}-{sede}"
            if not per_tappa[tid] and (sede == "commissione" or not a["n"]):   # una lettura senza emendamenti non ha tappe
                continue
            tappe.append({"id": tid, "atto": atto, "sede": sede, "label": f"{casa}, {'commissione' if sede == 'commissione' else 'Aula'}",
                          "chamber": ramo, "text": testo, "note": None})
            prima = passi[-1]["version"] if passi else None
            passi.append({"id": tid, "chamber": casa, "label": ("Commissione" if sede == "commissione" else "Aula") + (f", {lettura} lettura" if len(letture) > 1 else ""),
                          "date": None, "version": testo, "stage": tid, "changesFrom": testo if testo and testo != prima else None, "changesLabel": None})
        ultima_uscita = uscita or ultima_uscita
    if not versioni:
        return None
    if ultima_uscita and len(letture) > 1:
        passi.append({"id": "legge", "chamber": "Legge", "label": "Ultimo testo approvato", "date": None, "version": ultima_uscita,
                      "stage": "approvati", "changesFrom": ultima_uscita, "changesLabel": None})

    # ancoraggi al comma, voti in Aula, subemendamenti e testi identici
    testo_di = {t["id"]: t["text"] for t in tappe}
    voti_aula = {a["uri"]: _voti_aula(c, a["number"]) for a in letture if a["chamber"] == "camera"}
    per_uri = {a["uri"]: a for a in letture}
    atto_di = {f"{sigla_atto(a)}-{s}": a["uri"] for a in letture for s in ("commissione", "assemblea")}
    emendamenti = [e for e in emendamenti if e["stage"] in testo_di]
    # in Aula lo stesso emendamento si ristampa nel fascicolo di ogni seduta in cui l'esame continua: se ne tiene uno,
    # l'ultimo, con l'esito, le firme e la data che le copie hanno
    unici: dict[tuple, dict] = {}
    for e in emendamenti:
        prima = unici.get(k := (e["stage"], e["number"], e["hash"]))
        if prima:
            for campo in ("outcome", "outcome_raw", "signers"):
                e[campo] = e[campo] or prima[campo]
            e["date"] = prima["date"] or e["date"]
        unici[k] = e
    emendamenti = list(unici.values())
    for e in emendamenti:
        if testo_di[e["stage"]]:
            e["comma"], e["letter"] = ancora(e["text"])
        if e["stage"].endswith("-assemblea"):
            e["vote"] = voti_aula.get(atto_di[e["stage"]], {}).get(e["number"])
            e["outcome"] = e["outcome"] or (e["vote"]["outcome"] if e["vote"] else None)
    per_numero = {(e["stage"], e["number"]): e for e in emendamenti}
    for e in emendamenti:
        bersaglio = re.match(r"\s*All'emendamento\s+([\w./-]+?)[,\s]", e["text"] or "")
        n = bersaglio.group(1) if bersaglio else (e["number"].split("/")[0] if "/" in e["number"] else None)
        p = per_numero.get((e["stage"], n)) if n and n != e["number"] else None
        if p:
            e["parent"], e["kind"], e["comma"], e["letter"] = p["id"], "subEmendamento", None, None
    stessi: dict[tuple, list[dict]] = defaultdict(list)
    for e in emendamenti:
        if e["text"] and len(e["text"]) > 40:
            stessi[(e["stage"], e["hash"])].append(e)
    for xs in stessi.values():
        gruppi = {s["group"] for x in xs for s in x["signers"] if s["first"] and s["group"]}
        if len(xs) > 1 and len(gruppi) > 1:
            for e in xs:
                e["identical"] = sorted(x["id"] for x in xs if x is not e)
                e["identical_groups"] = sorted(gruppi)

    cambi, ordine = [], [v["id"] for v in versioni]
    for i in range(1, len(ordine)):
        vecchio, nuovo = ordine[i - 1], ordine[i]
        prodotto = {t["id"] for t in tappe if t["text"] == vecchio}
        approvati = [e for e in emendamenti if e["stage"] in prodotto and e["outcome"] == "approvato"]
        cambi += [x | {"version": nuovo} for x in modifiche(per_versione[vecchio], per_versione[nuovo], approvati)]

    for uri, vs in _voti_finali(c, list(per_uri)).items():
        a = per_uri[uri]
        ramo = "C" if a["chamber"] == "camera" else "S"
        casa = "alla Camera" if ramo == "C" else "al Senato"
        for v in vs:
            seduta = re.search(r"sed(\d+)", v["sitting"] or "")
            eventi.append({"date": v["date"].isoformat(), "chamber": ramo, "stage": None,
                           "label": f"Approvazione definitiva {casa}" if a is letture[-1] and definitivo(stato(a["chamber"], a["status"])) and v is vs[-1]
                                    else f"Voto finale {casa}",
                           "result": {"id": v["uri"], "session": int(seduta.group(1)) if seduta else None, "date": v["date"].isoformat(),
                                      "description": v["description"] or v["title"], "outcome": "approvato" if v["approved"] else "respinto",
                                      "in_favor": v["favor"], "against": v["against"], "abstained": v["abstain"], "secret": bool(v["secret"]),
                                      "url": (f"https://www.camera.it/leg19/410?idSeduta={int(seduta.group(1)):04d}&tipo=votazioni"
                                              if ramo == "C" and seduta else v["source_url"]),
                                      "by_group": [] if v["secret"] else _per_gruppo(c, v["uri"])}})
    eventi.sort(key=lambda e: (e["date"] or "").replace("-", ""))
    for t in tappe:
        t["count"] = sum(1 for e in emendamenti if e["stage"] == t["id"] and not e["parent"])
        t["approved"] = sum(1 for e in emendamenti if e["stage"] == t["id"] and e["outcome"] == "approvato")
    for p in passi:
        date = sorted(e["date"] for e in emendamenti if e["stage"] == p["stage"] and e["date"])
        p["date"] = date[0] if date else None

    stati = [stato(a["chamber"], a["status"]) for a in letture]
    return {"bill": {"slug": _slug_esterno(slug), "title": letture[0]["title"], "short": titolo_breve(letture[0]["title"]),
                     "numbers": [sigla_atto(a).replace(".", ". ") for a in letture], "proponents": "", "links": {},
                     "stato": stati[-1],
                     "definitiva": next((("C" if a["chamber"] == "camera" else "S") for a, s in zip(letture, stati) if definitivo(s)), None)},
            "versions": versioni, "stages": tappe, "steps": passi, "events": eventi,
            "amendments": emendamenti, "changes": cambi, "majority": MAGGIORANZA}


def _risposta(c: psycopg.Connection, slug: str):
    if not re.fullmatch(r"[\w-]{1,40}", slug):
        raise HTTPException(404, "legge non trovata")
    dati = _in_memoria(f"legge:{slug}", lambda: legge(c, slug))
    if dati is None:
        raise HTTPException(404, "legge non trovata")
    return JSONResponse(dati)


@router.get("/dati/emendamenti/legge-elettorale.json")
def legge_elettorale(c: Db):
    return _risposta(c, ELETTORALE[1])


@router.get("/dati/emendamenti/leggi/{slug}.json")
def una_legge(c: Db, slug: str):
    return _risposta(c, ELETTORALE[1] if slug == ELETTORALE[0] else slug)
