"""Schede di deputati e senatori per il sito, dal Postgres v3, nel formato che il sito già legge
(il vecchio formato delle schede). Solo lettura.

Rotte: /dati/schede/{id}.json e /dati/schede/indice.json (deputati), /dati/senatori.json e /dati/senatori/{id}.json,
/dati/senato/seats.json (pianta statica), /dati/foto/senatori/{id}.jpg (dai dati del servizio, o rimando a senato.it),
/dati/anagrafica/{id}.json e /dati/aic?n= (prima SPARQL su dati.camera.it, ora dal v3).

Come nel vecchio formato: gruppi con la sigla breve, il Misto per componente; voti della Camera senza le missioni nel totale,
voti del Senato contati sulle votazioni tenute dopo l'inizio del mandato (il Senato non registra gli assenti);
interventi solo in Aula. I numeri valgono per il ramo della scheda."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from pipeline.ambiente import QUI, env

from .db import connessione, per_richiesta
from .strumenti.comune import LEGISLATURA, stessa_persona

router = APIRouter(include_in_schema=False)
Db = Annotated[psycopg.Connection, Depends(per_richiesta)]
SITO = Path(__file__).resolve().parents[1] / "sito"
DURATA = 3600                       # i dati cambiano una volta per notte: l'indice e l'elenco restano in memoria un'ora

# ---------- gruppi: la sigla breve del vecchio formato dal nome nel v3 ----------

SIGLE = [(r"^fratelli d'italia", "FdI"), (r"^partito democratico", "PD"), (r"^lega", "Lega"), (r"^forza italia", "FI"),
         (r"^movimento 5 stelle", "M5S"), (r"^alleanza verdi", "AVS"), (r"^azione", "Azione"), (r"^italia viva", "IV"),
         (r"^noi moderati", "NM"), (r"^civici d'italia", "Civici"), (r"^per le autonomie", "Aut"), (r"^misto$", "Misto")]
NOMI = {  # il nome per esteso del vecchio formato, dove il v3 lo scrive diverso
    "Azione - Popolari Europeisti Riformatori - Renew Europe": "Azione - Popolari europeisti riformatori - Renew Europe",
    "Italia Viva - Casa Riformista": "Italia Viva - Casa riformista",
    "MoVimento 5 Stelle": "Movimento 5 Stelle",
    "Civici d'Italia-UDC-Noi Moderati (Noi con l'Italia, Coraggio Italia, Italia al Centro)-MAIE-Centro Popolare":
        "Civici d'Italia - UDC - Noi Moderati - MAIE - Centro Popolare",
}
COMPONENTI = {"+Europa - Stati Uniti d'Europa": "+Europa", "Minoranze Linguistiche": "Min. Ling.", "Sud Chiama Nord": "SCN",
              "Futuro Nazionale Vannacci - Free": "FNV", "Alleanza Verdi e Sinistra": "AVS", "Azione-Renew Europe": "Azione",
              "Avanti PSI": "PSI", "Avanti PSI - Progetto Civico Italia": "PSI", "Italia Domani - Marco Rizzo": "ID-MR",
              "Partito della Rifondazione Comunista - Sinistra Europea - Open Sinistra": "PRC-SE-OS"}
RUOLI_GRUPPO = {"leader": "Presidente del gruppo", "deputy_leader": "Vicepresidente del gruppo",
                "secretary": "Segretario del gruppo", "treasurer": "Tesoriere del gruppo"}
RUOLI_ORGANO = {"chair": "Presidente", "vice_chair": "Vicepresidente", "secretary": "Segretario", "quaestor": "Questore",
                "group_whip": "Capogruppo"}
# le commissioni permanenti della Camera: il v3 ha solo «I Commissione», il sito mostra il nome con la competenza
PERMANENTI_CAMERA = {
    "I": "Affari Costituzionali, della Presidenza del Consiglio e Interni", "II": "Giustizia",
    "III": "Affari Esteri e Comunitari", "IV": "Difesa", "V": "Bilancio, Tesoro e Programmazione", "VI": "Finanze",
    "VII": "Cultura, Scienza e Istruzione", "VIII": "Ambiente, Territorio e Lavori Pubblici",
    "IX": "Trasporti, Poste e Telecomunicazioni", "X": "Attività Produttive, Commercio e Turismo",
    "XI": "Lavoro Pubblico e Privato", "XII": "Affari Sociali", "XIII": "Agricoltura", "XIV": "Politiche dell'Unione Europea"}


def sigla(nome: str | None) -> str:
    for r, s in SIGLE:
        if nome and re.search(r, nome, re.I):
            return s
    return nome or "?"


def nome_gruppo(nome: str | None) -> str:
    return NOMI.get(nome or "", nome or "")


def nome_organo(nome: str, ramo: str) -> str:
    m = re.fullmatch(r"([IVX]+) Commissione", nome)
    if ramo == "camera" and m and m.group(1) in PERMANENTI_CAMERA:
        return f"{nome} ({PERMANENTI_CAMERA[m.group(1)]})"
    return nome


def _iso(d) -> str | None:
    return d.isoformat() if d else None


def _compatta(d) -> str | None:
    return d.strftime("%Y%m%d") if d else None


def _parola(w: str) -> str:
    return "-".join("'".join(p[:1].upper() + p[1:].lower() for p in x.split("'")) for x in w.split("-"))


def nome_proprio(t: str | None) -> str:
    return " ".join(_parola(w) for w in (t or "").split())


# ---------- estratti degli interventi, come nel vecchio formato ----------

ESTRATTO = 300
_CORTESIA = re.compile(r"^\s*((grazie|signor[ae]?|signora|presidente|onorevoli|colleghi|colleghe|rappresentant[ei] del governo|"
                       r"sottosegretari[oa]|ministr[oa]|vice ?ministr[oa]|cari|care|e|,|\.|!)\s*)+", re.I)
_ORE = re.compile(r"\s*\(ore [^)]*\)\.?")


def titolo_pulito(t: str | None) -> str | None:
    if not t:
        return None
    t = re.sub(r"\s+", " ", _ORE.sub("", t.replace(" ", " "))).strip().rstrip(" .")
    return t or None


def estratto(testo: str | None) -> str:
    t = re.sub(r"\s+", " ", (testo or "").replace(" ", " ")).strip()
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    senza = _CORTESIA.sub("", t)
    if len(senza) > 40:
        t = senza[:1].upper() + senza[1:]
    if len(t) <= ESTRATTO:
        return t
    taglio = t[:ESTRATTO - 1]
    if taglio.rfind(" ") > ESTRATTO * 0.6:
        taglio = taglio[:taglio.rfind(" ")]
    return taglio.rstrip(" ,;:.") + "…"


def url_stenografico(numero: int, item: str) -> str:
    sed = f"{numero:04d}"
    ancora = item.rsplit(":", 1)[-1]
    return f"https://www.camera.it/leg{LEGISLATURA}/410?idSeduta={sed}&tipo=stenografico#sed{sed}.stenografico.{ancora}"


FOTO_SENATORI = QUI / env("CARTELLA_DATI", "dati") / "foto" / "senatori"   # la scrive il passo senato_foto


def foto_senato(did: str) -> str:
    return f"https://www.senato.it/leg/{LEGISLATURA}/Immagini/Senatori/{int(did):08d}.jpg"


def foto_camera(pid: str) -> str:
    return f"https://documenti.camera.it/_dati/leg{LEGISLATURA}/schededeputatinuovosito/fotoDefinitivo/big/d{pid}.jpg"


# ---------- conti di un ramo, per tutti in una volta (indice ed elenco) o per una persona ----------

SQL_VOTI = """
SELECT b.person,
       count(*) FILTER (WHERE b.result NOT IN ('mission', 'chair')) AS total,
       count(*) FILTER (WHERE b.result = 'favor') AS favor, count(*) FILTER (WHERE b.result = 'against') AS against,
       count(*) FILTER (WHERE b.result = 'abstain') AS abstain, count(*) FILTER (WHERE b.result = 'absent') AS absent
FROM ballot b JOIN vote v ON v.uri = b.vote
WHERE v.chamber = %(ramo)s AND v.legislature = %(leg)s AND (%(ids)s::text[] IS NULL OR b.person = ANY(%(ids)s))
GROUP BY b.person"""
SQL_INTERVENTI = """
SELECT s.person, count(*) AS n, count(DISTINCT t.uri) AS sedute, min(t.date) AS prima, max(t.date) AS ultima
FROM speech s JOIN agenda_item i ON i.uri = s.item JOIN sitting t ON t.uri = i.sitting
WHERE t.body = %(aula)s AND s.person IS NOT NULL AND (%(ids)s::text[] IS NULL OR s.person = ANY(%(ids)s))
GROUP BY s.person"""
SQL_FIRME = """
SELECT sp.person, count(DISTINCT a.uri) FILTER (WHERE sp.first) AS prima, count(DISTINCT a.uri) FILTER (WHERE NOT sp.first) AS cofirma
FROM act_sponsor sp JOIN act a ON a.uri = sp.act
WHERE a.chamber = %(ramo)s AND a.legislature = %(leg)s AND (%(ids)s::text[] IS NULL OR sp.person = ANY(%(ids)s))
GROUP BY sp.person"""
SQL_TENUTE = """
SELECT count(*) AS n FROM vote WHERE chamber = 'senato' AND legislature = %(leg)s AND date >= %(da)s
  AND (%(a)s::date IS NULL OR date <= %(a)s)"""


def _per_persona(c: psycopg.Connection, sql: str, ramo: str, ids: list[str] | None) -> dict[str, dict]:
    p = {"ramo": ramo, "leg": LEGISLATURA, "ids": ids, "aula": f"it:{ramo}:{LEGISLATURA}:aula"}
    return {r["person"]: r for r in c.execute(sql, p)}


def _somma(righe: list[dict], chiavi: tuple[str, ...]) -> dict | None:
    """Una persona con due schede (Camera e Senato) conta le righe di tutte e due."""
    if not righe:
        return None
    return {k: sum(r[k] or 0 for r in righe) for k in chiavi}


def voti_camera(r: dict | None) -> dict | None:
    if not r or not r["total"]:
        return None
    return {**{k: r[k] for k in ("total", "favor", "against", "abstain", "absent")},
            "participationPct": round(100 * (r["total"] - r["absent"]) / r["total"], 1)}


def voti_senato(r: dict | None, tenute: int) -> dict | None:
    if not r or not tenute:
        return None
    espressi = r["favor"] + r["against"] + r["abstain"]
    totale = max(tenute, espressi)
    return {"total": totale, "favor": r["favor"], "against": r["against"], "abstain": r["abstain"],
            "absent": totale - espressi, "participationPct": round(100 * espressi / totale, 1)}


def aggiornato_al(c: psycopg.Connection, ramo: str) -> str | None:
    r = c.execute("SELECT max(date) AS d FROM sitting WHERE body = %s AND status = 'held'",
                  (f"it:{ramo}:{LEGISLATURA}:aula",)).fetchone()
    return _iso(r["d"])


# ---------- in carica: gruppo e componente di oggi ----------

SQL_IN_CARICA = """
SELECT p.uri, p.camera_id, p.senato_id, p.given_name, p.family_name, p.sort_name, m.start_date AS inizio,
       g.name AS gruppo, gm.start_date AS dal, gm.grp AS g_uri, k.name AS componente
FROM mandate m JOIN person p ON p.uri = m.person
LEFT JOIN LATERAL (SELECT x.grp, x.start_date FROM membership x JOIN grp y ON y.uri = x.grp AND y.kind = 'group'
                   WHERE x.person = p.uri AND y.chamber = m.chamber AND y.legislature = m.legislature
                     AND x.start_date <= current_date AND (x.end_date IS NULL OR x.end_date >= current_date)
                   ORDER BY x.start_date DESC LIMIT 1) gm ON true
LEFT JOIN grp g ON g.uri = gm.grp
LEFT JOIN LATERAL (SELECT y.name FROM membership x JOIN grp y ON y.uri = x.grp AND y.kind = 'misto_component'
                   WHERE x.person = p.uri AND y.chamber = m.chamber AND y.legislature = m.legislature
                     AND x.start_date <= current_date AND (x.end_date IS NULL OR x.end_date >= current_date)
                   ORDER BY x.start_date DESC LIMIT 1) k ON true
WHERE m.chamber = %(ramo)s AND m.legislature = %(leg)s AND m.end_date IS NULL
  AND (%(uri)s::text IS NULL OR p.uri = %(uri)s)
ORDER BY p.sort_name"""

SQL_CARICHE_GRUPPO = """
SELECT o.person, o.target, o.title, o.start_date, o.end_date FROM office o
WHERE o.person = ANY(%(ids)s) AND o.target LIKE %(prefisso)s AND o.title = ANY(%(titoli)s)"""


def _ruolo_gruppo(cariche: list[dict], gruppo: str | None, quando: dt.date | None = None) -> str | None:
    """La carica nel gruppo alla data (oggi, se manca), la più alta se sono più d'una."""
    quando = quando or dt.date.today()
    ordine = list(RUOLI_GRUPPO)
    vive = [o for o in cariche if o["target"] == gruppo and o["start_date"] <= quando
            and (o["end_date"] is None or o["end_date"] >= quando)]
    vive.sort(key=lambda o: ordine.index(o["title"]))
    return RUOLI_GRUPPO[vive[0]["title"]] if vive else None


def _cariche_gruppo(c: psycopg.Connection, ids: list[str], ramo: str) -> list[dict]:
    return c.execute(SQL_CARICHE_GRUPPO, {"ids": ids, "prefisso": f"it:{ramo}:{LEGISLATURA}:group:%",
                                          "titoli": list(RUOLI_GRUPPO)}).fetchall()


# ---------- la scheda ----------

def _ruolo_istituzionale(c: psycopg.Connection, ids: list[str], ramo: str) -> str | None:
    """Una sola carica, la più alta in corso: Presidenza della Camera o del Senato, governo, presidenza di commissione,
    presidenza del gruppo, ricomposta dalle cariche."""
    oggi = dt.date.today()
    righe = c.execute("""
        SELECT o.title, o.title_raw, o.target, b.name AS organo, b.kind AS tipo, g.name AS gruppo
        FROM office o LEFT JOIN body b ON b.uri = o.target LEFT JOIN grp g ON g.uri = o.target
        WHERE o.person = ANY(%(ids)s) AND o.start_date <= %(oggi)s AND (o.end_date IS NULL OR o.end_date >= %(oggi)s)""",
        {"ids": ids, "oggi": oggi}).fetchall()
    assemblea = "Camera dei Deputati" if ramo == "camera" else "Senato della Repubblica"
    for r in righe:      # Presidente e vicepresidenti dell'Assemblea: cariche dell'Ufficio di Presidenza
        if r["tipo"] == "presidency" and (r["organo"] or "").startswith(("Ufficio di Presidenza", "Consiglio di Presidenza")) \
                and r["title"] in ("chair", "vice_chair"):
            return f"{RUOLI_ORGANO[r['title']]} {'della' if ramo == 'camera' else 'del'} {assemblea}"
    for r in righe:
        if r["target"].startswith("it:gov:"):
            return r["title_raw"]
    for t in ("chair", "vice_chair", "secretary"):
        for r in righe:
            if r["title"] == t and r["tipo"] == "standing_committee":
                return f"{RUOLI_ORGANO[t]} {nome_organo(r['organo'], ramo).upper()}"
    for r in righe:
        if r["title"] == "leader" and r["gruppo"]:
            return f"Presidente del Gruppo {r['gruppo'].upper()}"
    return None


def scheda(c: psycopg.Connection, ramo: str, pid: str) -> dict | None:
    c.execute(LENTE)                                 # i voti di una persona a freddo: migliaia di pagine di ballot
    uri = f"it:person:{ramo}:{pid}"
    base = c.execute(SQL_IN_CARICA.replace("AND m.end_date IS NULL", ""), {"ramo": ramo, "leg": LEGISLATURA, "uri": uri}).fetchone()
    if base is None:
        return None
    p = c.execute("SELECT * FROM person WHERE uri = %s", (uri,)).fetchone()
    ids = stessa_persona(c, uri)
    prefisso = f"it:{ramo}:{LEGISLATURA}:"
    cariche_g = _cariche_gruppo(c, ids, ramo)

    gruppi = c.execute("""
        SELECT x.grp, x.start_date, x.end_date, name_at(y.uri, x.start_date) AS name, y.kind FROM membership x JOIN grp y ON y.uri = x.grp
        WHERE x.person = ANY(%s) AND y.uri LIKE %s ORDER BY x.start_date DESC""", (ids, prefisso + "%")).fetchall()
    storia = [{"acronym": sigla(g["name"]), "name": nome_gruppo(g["name"]), "from": _iso(g["start_date"]), "to": _iso(g["end_date"]),
               "role": _ruolo_gruppo(cariche_g, g["grp"], g["end_date"] or dt.date.today())}
              for g in gruppi if g["kind"] == "group"]
    componenti = [{"to": _iso(g["end_date"]), "name": g["name"], "from": _iso(g["start_date"])} for g in gruppi if g["kind"] == "misto_component"]

    organi = c.execute("""
        SELECT DISTINCT s.body, b.name, s.start_date, s.end_date FROM seat s JOIN body b ON b.uri = s.body
        WHERE s.person = ANY(%s) AND b.uri LIKE %s""", (ids, prefisso + "%")).fetchall()
    cariche_o = c.execute("""SELECT target, title, start_date, end_date FROM office
                             WHERE person = ANY(%s) AND target LIKE %s AND title = ANY(%s)""",
                          (ids, prefisso + "body:%", ["chair", "vice_chair", "secretary", "quaestor"])).fetchall()
    commissioni, visti = [], set()
    for o in organi:
        if (o["name"], o["start_date"]) in visti:
            continue
        visti.add((o["name"], o["start_date"]))
        fine = o["end_date"] or dt.date.max
        ruolo = next((k for k in cariche_o if k["target"] == o["body"] and k["start_date"] <= fine
                      and (k["end_date"] is None or k["end_date"] >= o["start_date"])), None)
        commissioni.append({"name": nome_organo(o["name"], ramo), "from": _iso(o["start_date"]), "to": _iso(o["end_date"]),
                            "role": RUOLI_ORGANO[ruolo["title"]] if ruolo else None,
                            "roleFrom": _iso(ruolo["start_date"]) if ruolo else None, "roleTo": _iso(ruolo["end_date"]) if ruolo else None})
    commissioni.sort(key=lambda x: (x["to"] is not None, -int((x["to"] or "9999")[:4]), x["name"]))

    governo = {}
    for o in c.execute("""SELECT title_raw, start_date FROM office WHERE person = ANY(%s) AND target LIKE 'it:gov:%%'
                          ORDER BY start_date""", (ids,)):
        governo.setdefault(o["title_raw"], {"role": o["title_raw"], "from": _iso(o["start_date"])})

    mandato = c.execute("""SELECT start_date, end_date FROM mandate WHERE person = %s AND chamber = %s AND legislature = %s
                           ORDER BY start_date LIMIT 1""", (uri, ramo, LEGISLATURA)).fetchone()
    date_sp = list(_per_persona(c, SQL_INTERVENTI, ramo, ids).values())
    sp = _somma(date_sp, ("n", "sedute"))
    firme = _somma(list(_per_persona(c, SQL_FIRME, ramo, ids).values()), ("prima", "cofirma")) or {}
    voti = _somma(list(_per_persona(c, SQL_VOTI, ramo, ids).values()), ("total", "favor", "against", "abstain", "absent"))
    if ramo == "camera":
        statistiche = voti_camera(voti)
    else:
        tenute = c.execute(SQL_TENUTE, {"leg": LEGISLATURA, "da": mandato["start_date"], "a": mandato["end_date"]}).fetchone()["n"]
        statistiche = voti_senato(voti, tenute)

    recenti = []
    if ramo == "camera":
        recenti = [{"date": _iso(r["date"]), "session": r["number"], "debate": titolo_pulito(r["title"]), "excerpt": estratto(r["text"]),
                    "url": url_stenografico(r["number"], r["item"])} for r in c.execute("""
            SELECT t.date, t.number, i.uri AS item, i.title, left(s.text, 1200) AS text
            FROM speech s JOIN agenda_item i ON i.uri = s.item JOIN sitting t ON t.uri = i.sitting
            WHERE s.person = ANY(%s) AND t.body = %s ORDER BY t.date DESC, s.ord DESC LIMIT 10""",
            (ids, f"it:camera:{LEGISLATURA}:aula"))]

    misto = sigla(base["gruppo"]) == "Misto" and base["componente"]
    scheda = {
        "id": pid, "name": nome_proprio(f"{p['given_name'] or ''} {p['family_name'] or ''}"),
        "firstName": nome_proprio(p["given_name"]), "lastName": nome_proprio(p["family_name"]),
        "photo": foto_camera(pid) if ramo == "camera" else f"/dati/foto/senatori/{pid}.jpg",
        "group": {"acronym": sigla(base["gruppo"]), "name": nome_gruppo(base["gruppo"]), "since": _iso(base["dal"]),
                  "role": _ruolo_gruppo(cariche_g, base["g_uri"])} if base["gruppo"] else None,
        "mistoComponent": {"name": base["componente"], "short": COMPONENTI.get(base["componente"], base["componente"])} if misto else None,
        "groupHistory": storia, "mistoComponents": componenti, "committees": commissioni,
        "governmentOffices": list(governo.values()), "institutionalRole": _ruolo_istituzionale(c, ids, ramo),
        "profession": p["profession"], "education": p["education"], "mandateStart": _iso(mandato["start_date"]),
        "cameraUrl": f"https://www.camera.it/deputati/elenco/{LEGISLATURA}-{pid}" if ramo == "camera" else None,
        "counts": {"speeches": (sp or {}).get("n", 0), "sessionsWithSpeeches": (sp or {}).get("sedute", 0),
                   "firstSpeech": _iso(min((r["prima"] for r in date_sp), default=None)),
                   "lastSpeech": _iso(max((r["ultima"] for r in date_sp), default=None)),
                   "actsPrimary": firme.get("prima", 0), "actsCosigned": firme.get("cofirma", 0)},
        "votes": statistiche, "recentSpeeches": recenti, "dataAsOf": aggiornato_al(c, ramo),
    }
    if ramo == "senato":
        scheda["senatoUrl"] = f"https://www.senato.it/composizione/senatori/elenco-alfabetico/scheda-attivita?did={pid}"
    return scheda


# ---------- indice dei deputati ed elenco dei senatori, in memoria per un'ora ----------

_memo: dict[str, tuple[float, dict]] = {}
_blocco = threading.Lock()


def _ricordato(chiave: str, calcola) -> dict:
    with _blocco:
        x = _memo.get(chiave)
        if x and time.monotonic() - x[0] < DURATA:
            return x[1]
    v = calcola()
    with _blocco:
        _memo[chiave] = (time.monotonic(), v)
    return v


def indice_deputati(c: psycopg.Connection) -> dict:
    """Una riga per deputato in carica con i numeri della scheda, per classifiche e confronti (chat del sito)."""
    righe = c.execute(SQL_IN_CARICA, {"ramo": "camera", "leg": LEGISLATURA, "uri": None}).fetchall()
    voti = _per_persona(c, SQL_VOTI, "camera", None)
    sp = _per_persona(c, SQL_INTERVENTI, "camera", None)
    firme = _per_persona(c, SQL_FIRME, "camera", None)
    oggi = dt.date.today()
    cariche = {r["person"] for r in c.execute("""SELECT DISTINCT person FROM office WHERE target LIKE 'it:gov:%%'
                                                 AND start_date <= %s AND (end_date IS NULL OR end_date >= %s)""", (oggi, oggi))}
    ruoli = {r["person"]: r["title_raw"] for r in c.execute("""
        SELECT DISTINCT ON (o.person) o.person, o.title_raw FROM office o JOIN body b ON b.uri = o.target
        WHERE b.uri LIKE 'it:camera:19:body:%%' AND b.kind = 'presidency' AND o.title IN ('chair', 'vice_chair')
          AND (b.name LIKE 'Ufficio di Presidenza%%') AND (o.end_date IS NULL OR o.end_date >= %s)
        ORDER BY o.person, o.title""", (oggi,))}
    deputati = []
    for r in righe:
        u, v = r["uri"], voti_camera(voti.get(r["uri"]))
        g = sigla(r["gruppo"])
        deputati.append({"id": r["camera_id"], "n": nome_proprio(f"{r['given_name']} {r['family_name']}"),
                         "g": COMPONENTI.get(r["componente"], g) if g == "Misto" and r["componente"] else g,
                         "pp": v and v["participationPct"], "tot": v and v["total"], "ass": v and v["absent"],
                         "sp": (sp.get(u) or {}).get("n", 0), "ap": (firme.get(u) or {}).get("prima", 0),
                         "ac": (firme.get(u) or {}).get("cofirma", 0),
                         "ruolo": (f"{RUOLI_ORGANO.get('chair' if ruoli[u].lower().startswith('presidente') else 'vice_chair')} della Camera dei Deputati"
                                   if u in ruoli else None), "gov": u in cariche})
    return {"dataAsOf": aggiornato_al(c, "camera"), "deputati": deputati}


def elenco_senatori(c: psycopg.Connection) -> dict:
    righe = c.execute(SQL_IN_CARICA, {"ramo": "senato", "leg": LEGISLATURA, "uri": None}).fetchall()
    cariche = _cariche_gruppo(c, [r["uri"] for r in righe], "senato")
    per_persona: dict[str, list[dict]] = {}
    for o in cariche:
        per_persona.setdefault(o["person"], []).append(o)
    gruppi: dict[str, str] = {}
    senatori = []
    for i, r in enumerate(righe):
        did, g = r["senato_id"], sigla(r["gruppo"])
        gruppi.setdefault(g, nome_gruppo(r["gruppo"]))
        senatori.append({"id": did, "name": nome_proprio(f"{r['given_name']} {r['family_name']}"), "last": nome_proprio(r["family_name"]),
                         "group": g, "groupName": nome_gruppo(r["gruppo"]),
                         "component": COMPONENTI.get(r["componente"], r["componente"]) if g == "Misto" and r["componente"] else None,
                         "role": _ruolo_gruppo(per_persona.get(r["uri"], []), r["g_uri"]),
                         "photo": f"/dati/foto/senatori/{did}.jpg", "order": i, "seat": None})   # il posto in Aula non sta nel v3
    return {"dataAsOf": aggiornato_al(c, "senato"), "legislature": LEGISLATURA, "chamber": "senato",
            "groups": [{"acronym": k, "name": v} for k, v in gruppi.items()], "deputies": senatori,
            "seatsSource": None, "seatsAsOf": None}


# ---------- anagrafica e atti di sindacato ispettivo, nel formato di dati.camera.it ----------

def anagrafica(c: psycopg.Connection, pid: str) -> dict | None:
    """Gli stessi campi della query SPARQL del prototipo. Data e titolo dell'elezione non stanno nel v3: restano vuoti."""
    r = c.execute("""
        SELECT p.birth_date, p.birth_place, p.gender, p.education, p.profession, p.source_uri, m.start_date, m.validated,
               m.constituency, m.college, m.system
        FROM person p LEFT JOIN LATERAL (SELECT * FROM mandate WHERE person = p.uri AND chamber = 'camera' AND legislature = %s
                                         ORDER BY start_date LIMIT 1) m ON true
        WHERE p.uri = %s""", (LEGISLATURA, f"it:person:camera:{pid}")).fetchone()
    if r is None:
        return None
    nato = "nata" if r["gender"] == "F" else "nato"
    return {"nascitaL": f"{nato} a {r['birth_place'].upper()}, il {r['birth_date']:%d.%m.%Y}" if r["birth_place"] and r["birth_date"] else None,
            "nascita": _compatta(r["birth_date"]), "descr": "; ".join(x for x in (r["education"], r["profession"]) if x) or None,
            "inizio": _compatta(r["start_date"]), "convalida": _iso(r["validated"]), "circ": r["constituency"], "coll": r["college"],
            "tipo": {"majoritarian": "maggioritario", "proportional": "proporzionale"}.get(r["system"] or "", r["system"]),
            "elez": None, "data": None, "fonte": r["source_uri"] or f"http://dati.camera.it/ocd/persona.rdf/p{pid}"}


def atto_aic(c: psycopg.Connection, num: str) -> dict:
    """Interrogazioni, interpellanze, mozioni e risoluzioni della Camera, con testo, autore e ministero destinatario."""
    a = c.execute("SELECT * FROM act WHERE uri = %s", (f"it:camera:{LEGISLATURA}:aic:{num.replace('/', '-')}",)).fetchone()
    if a is None:
        return {}
    autore = c.execute("""
        SELECT upper(concat_ws(' ', p.family_name, p.given_name)) AS nome, upper(g.name) AS gruppo
        FROM act_sponsor s JOIN person p ON p.uri = s.person LEFT JOIN grp g ON g.uri = group_at(p.uri, %s)
        WHERE s.act = %s AND s.first LIMIT 1""", (a["date"], a["uri"])).fetchone()
    dest = c.execute("""SELECT upper(m.name) AS nome FROM act_addressee x JOIN ministry m ON m.uri = x.ministry
                        WHERE x.act = %s ORDER BY m.name LIMIT 1""", (a["uri"],)).fetchone()
    data = _compatta(a["date"]) + (f"-{_compatta(a['closed_date'])}" if a["closed_date"] and a["closed_date"] != a["date"] else "") if a["date"] else None
    return {"a": a["source_uri"], "titolo": a["title"], "tipo": a["kind_raw"], "testo": a["text"], "data": data,
            "autore": f"{autore['nome']} ({autore['gruppo']})" if autore and autore["gruppo"] else (autore or {}).get("nome"),
            "dest": dest and dest["nome"], "doc": a["card_url"], "concluso": "1" if a["concluded"] else "0"}


# ---------- rotte ----------

def _json(dati, codice: int = 200) -> JSONResponse:
    return JSONResponse(dati, status_code=codice, headers={"Cache-Control": "public, max-age=600"} if codice == 200 else None)


LENTE = "SET statement_timeout = '30s'"     # gli aggregati sui voti di tutta la Camera superano gli 8 s del ruolo


def scalda(ogni: float = DURATA / 2) -> None:
    """Ricalcola indice dei deputati ed elenco dei senatori prima che scadano, così nessun visitatore aspetta gli
    aggregati sui voti. Gira in un thread del servizio, dall'avvio; un errore aspetta il giro dopo."""
    while True:
        try:
            with connessione() as c:
                c.execute(LENTE)
                for chiave, calcola in (("indice", indice_deputati), ("senatori", elenco_senatori), ("ultimi-voti", ultimi_voti)):
                    v = calcola(c)
                    with _blocco:
                        _memo[chiave] = (time.monotonic(), v)
        except psycopg.Error as e:
            logging.getLogger("parliamentrag.sito").warning("schede non ricalcolate: %s", type(e).__name__)
        time.sleep(ogni)


def ultimi_voti(c: psycopg.Connection, quanti: int = 3) -> list[dict]:
    """Le ultime votazioni finali della home, dalle sedute più recenti: le stesse che il sito chiedeva seduta per seduta."""
    from . import pubblico
    righe: list[dict] = []
    for s in pubblico.esegui(c, "list_sessions", {"limit": 25}).get("sessions") or []:
        if len(righe) >= quanti:
            break
        voti = [v for v in pubblico.esegui(c, "get_session_votes", {"session_id": s["id"]}).get("votes") or [] if v.get("final_vote")]
        righe += [{"v": v, "s": {"date": s["date"], "chamber": s["chamber"]}} for v in voti[:quanti - len(righe)]]
    return righe


@router.get("/dati/ultimi-voti.json")
def r_ultimi_voti(c: Db):
    return _json(_ricordato("ultimi-voti", lambda: ultimi_voti(c)))


@router.get("/dati/schede/indice.json")
def r_indice(c: Db):
    def calcola():
        c.execute(LENTE)
        return indice_deputati(c)
    return _json(_ricordato("indice", calcola))


@router.get("/dati/schede/{pid}.json")
def r_scheda_deputato(c: Db, pid: str):
    if not re.fullmatch(r"\d{3,7}", pid):
        raise HTTPException(404, "scheda non trovata")
    d = scheda(c, "camera", pid)
    return _json(d) if d else _json({"errore": "scheda non trovata"}, 404)


@router.get("/dati/senatori.json")
def r_senatori(c: Db):
    return _json(_ricordato("senatori", lambda: elenco_senatori(c)))


@router.get("/dati/senatori/{did}.json")
def r_scheda_senatore(c: Db, did: str):
    if not re.fullmatch(r"\d{1,7}", did):
        raise HTTPException(404, "non trovato")
    d = scheda(c, "senato", did)
    return _json(d) if d else _json({"errore": "non trovato"}, 404)


@router.get("/dati/senato/seats.json")
def r_pianta_senato():
    f = SITO / "dati" / "senato" / "seats.json"
    if not f.is_file():
        return _json({"errore": "non trovato"}, 404)
    return _json(json.loads(f.read_text()))


@router.get("/dati/foto/senatori/{did}.jpg")
def r_foto_senatore(c: Db, did: str):
    if not re.fullmatch(r"\d{1,7}", did):
        raise HTTPException(404, "non trovato")
    # senato.it serve le foto dietro il WAF, che a un browser nuovo risponde con la pagina di verifica: le foto stanno
    # nel database (person_photo, le scrive il passo senato_foto) o fra i dati del servizio; se no, il rimando a senato.it
    r = c.execute("SELECT image, media_type FROM person_photo WHERE person = %s", (f"it:person:senato:{int(did)}",)).fetchone()
    if r:
        return Response(bytes(r["image"]), media_type=r["media_type"], headers={"Cache-Control": "public, max-age=86400"})
    f = FOTO_SENATORI / f"{int(did)}.jpg"
    if f.is_file():
        return FileResponse(f, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    return RedirectResponse(foto_senato(did), status_code=302, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/dati/anagrafica/{pid}.json")
def r_anagrafica(c: Db, pid: str):
    if not re.fullmatch(r"\d{3,7}", pid):
        raise HTTPException(404, "non trovato")
    d = anagrafica(c, pid)
    return _json(d) if d else _json({"errore": "deputato non trovato"}, 404)


@router.get("/dati/aic")
def r_aic(c: Db, n: Annotated[str, Query(pattern=r"^\d/\d{4,6}(?:/\d+)?$")]):
    return _json(atto_aic(c, n))
