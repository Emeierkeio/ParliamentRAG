"""Statistiche di visita fatte da noi, senza cookie e senza salvare l'IP (schema/sito.sql, tabella sito.visita).

La pagina manda a POST /api/visita il percorso, la provenienza, la larghezza della finestra e la lingua; il servizio
aggiunge le domande alla chat e i fascicoli (registra). Il visitatore è un'impronta di IP, browser e giorno con la
chiave LIMITE_SALE: conta i visitatori unici del giorno e non si ricollega ai giorni dopo. Il pannello /statistiche e i
suoi dati (/api/statistiche) stanno dietro un login (STATISTICHE_UTENTE, STATISTICHE_PASSWORD); senza, non esistono.

Paese e regione vengono dall'IP con il file DB-IP «IP to City Lite» (CC BY 4.0, dati/geo, aggiornato ogni mese da
deploy/vps/geoip.sh): la ricerca è in locale e l'IP non si salva. Gli attivi ora vengono da /api/presenza, che ogni
pagina aperta e in primo piano chiama una volta al minuto: le impronte restano in memoria, non nel database.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import logging
import random
import re
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from pipeline.ambiente import env

from . import agente
from .db import connessione_sito

# i vettori della ricerca per significato, come in pipeline/vettori.py (che il container web non ha): da tenere allineati
MODELLO_VETTORI = "text-embedding-3-large"
DOLLARI_PER_MILIONE = 0.065
from .rete import ip

router = APIRouter()
log = logging.getLogger("parliamentrag.statistiche")
PAGINA = Path(__file__).parent / "statistiche.html"
MAPPA = Path(__file__).parent / "regioni-italia.json"      # confini delle regioni ISTAT semplificati, per la mappa del pannello
NOSTRI = ("parliamentrag.it", "www.parliamentrag.it", "mcp.parliamentrag.it")
ROBOT = re.compile(r"bot|crawl|spider|slurp|headless|preview|monitor|curl|wget|python|httpx|go-http|scrapy", re.I)
GIORNI_TENUTI = 400
GEO = Path(env("GEOIP_FILE", "dati/geo/dbip-city-lite.mmdb"))
PRESENZA_S = 120                                    # attivo: un segnale negli ultimi 2 minuti (la pagina ne manda uno al minuto)
_presenze: dict[str, float] = {}
_geo: dict = {"lettore": None, "mtime": 0.0, "visto": 0.0}
_geo_lock = threading.Lock()


class Visita(BaseModel):
    p: str = Field(max_length=300)                   # percorso con il cancelletto: /#/strumenti/sedute
    r: str | None = Field(default=None, max_length=500)
    w: int | None = Field(default=None, ge=0, le=20000)
    l: str | None = Field(default=None, max_length=20)


def percorso(p: str) -> str:
    """Il percorso senza parametri e senza gli id delle conversazioni condivise (sono la chiave per leggerle)."""
    p = p.split("?")[0].split("&")[0][:200] or "/"
    return re.sub(r"(#/c/)[^/]+", r"\1…", p)


def provenienza(r: str | None) -> str | None:
    host = (urlsplit(r).hostname or "").lower() if r else ""
    return None if not host or host in NOSTRI or host in ("localhost", "127.0.0.1") else host.removeprefix("www.")


def dispositivo(w: int | None) -> str | None:
    return None if not w else "telefono" if w < 768 else "tablet" if w < 1100 else "computer"


def browser(ua: str) -> str:
    for nome, rx in (("Edge", r"Edg/"), ("Opera", r"OPR/"), ("Samsung", r"SamsungBrowser"), ("Firefox", r"Firefox/"),
                     ("Chrome", r"Chrome/|CriOS/"), ("Safari", r"Safari/")):
        if re.search(rx, ua):
            return nome
    return "altro"


def luogo(indirizzo: str) -> tuple[str | None, str | None]:
    """Paese (codice ISO) e regione dall'IP, con il file DB-IP in locale; (None, None) se il file manca o l'IP non c'è.
    Il file si riapre quando cambia (aggiornamento mensile), controllato al massimo una volta all'ora."""
    with _geo_lock:
        adesso = time.monotonic()
        if adesso - _geo["visto"] > 3600 or (_geo["lettore"] is None and adesso - _geo["visto"] > 60):
            _geo["visto"] = adesso
            try:
                m = GEO.stat().st_mtime
                if m != _geo["mtime"]:
                    import maxminddb                # solo qui: senza il file il servizio non lo carica
                    _geo["lettore"], _geo["mtime"] = maxminddb.open_database(str(GEO)), m
            except (OSError, ValueError) as e:
                log.warning("file dei paesi non letto: %s", type(e).__name__)
        lettore = _geo["lettore"]
    if lettore is None:
        return None, None
    try:
        d = lettore.get(indirizzo) or {}
    except ValueError:                              # indirizzo non valido
        return None, None
    sotto = d.get("subdivisions") or [{}]
    return (d.get("country") or {}).get("iso_code"), (sotto[0].get("names") or {}).get("en")


def _visitatore(indirizzo: str, ua: str, giorno: dt.date) -> str:
    return hmac.new(agente._sale(), f"{giorno.isoformat()}|{indirizzo}|{ua}".encode(), hashlib.sha256).hexdigest()[:20]


def _scrivi(req: Request, evento: str, p: str | None = None, r: str | None = None, w: int | None = None,
            lingua: str | None = None) -> None:
    ua = req.headers.get("user-agent", "")
    if ROBOT.search(ua):
        return
    oggi = dt.date.today()
    with connessione_sito() as c:
        if c is None:
            return
        indirizzo = ip(req)
        paese, regione = luogo(indirizzo)
        c.execute("""INSERT INTO sito.visita (giorno, evento, percorso, provenienza, dispositivo, browser, lingua, visitatore, paese, regione)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                  (oggi, evento, p, provenienza(r), dispositivo(w), browser(ua), (lingua or "")[:2].lower() or None,
                   _visitatore(indirizzo, ua, oggi), paese, regione))
        if random.random() < 0.002:                  # ogni tanto, via le righe più vecchie di 400 giorni
            c.execute("DELETE FROM sito.visita WHERE giorno < %s", (oggi - dt.timedelta(days=GIORNI_TENUTI),))


def registra(req: Request, evento: str) -> None:
    """Una domanda alla chat o un fascicolo, contati dal servizio: non deve mai fermare la risposta."""
    try:
        _scrivi(req, evento)
    except psycopg.Error as e:
        log.warning("statistica non scritta: %s", type(e).__name__)


@router.post("/api/visita", status_code=204)
def visita(req: Request, v: Visita) -> Response:
    try:
        _scrivi(req, "pagina", percorso(v.p), v.r, v.w, v.l)
    except psycopg.Error as e:
        log.warning("visita non scritta: %s", type(e).__name__)
    return Response(status_code=204)


@router.post("/api/presenza", status_code=204)
def presenza(req: Request) -> Response:
    """Una pagina aperta e in primo piano: l'impronta del giorno e l'ora, solo in memoria, per gli attivi ora."""
    ua = req.headers.get("user-agent", "")
    if not ROBOT.search(ua):
        adesso = time.monotonic()
        _presenze[_visitatore(ip(req), ua, dt.date.today())] = adesso
        for k in [k for k, t in _presenze.items() if adesso - t > PRESENZA_S]:
            _presenze.pop(k, None)
    return Response(status_code=204)


def attivi_ora() -> int:
    adesso = time.monotonic()
    return sum(1 for t in list(_presenze.values()) if adesso - t <= PRESENZA_S)


def _login(req: Request) -> None:
    utente, password = env("STATISTICHE_UTENTE", ""), env("STATISTICHE_PASSWORD", "")
    if not utente or not password:
        raise HTTPException(404)
    a = req.headers.get("authorization", "")
    try:
        u, _, pw = base64.b64decode(a.removeprefix("Basic ")).decode().partition(":") if a.startswith("Basic ") else ("", "", "")
    except ValueError:
        u, pw = "", ""
    if not (secrets.compare_digest(u, utente) and secrets.compare_digest(pw, password)):
        raise HTTPException(401, "serve il login", headers={"WWW-Authenticate": 'Basic realm="Statistiche ParliamentRAG"'})


@router.get("/statistiche", response_class=HTMLResponse, include_in_schema=False)
def pannello(req: Request) -> HTMLResponse:
    _login(req)
    pagina = PAGINA.read_text(encoding="utf-8").replace("/*MAPPA*/null", MAPPA.read_text(encoding="utf-8"))
    return HTMLResponse(pagina, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


def _costi(c: psycopg.Connection, dal: dt.date) -> dict:
    """Spesa OpenAI e numeri della chat: sito.spesa (ogni chiamata: chat, fascicoli, traduzioni), le viste registro.uso_chat
    e registro.spesa_vettori (schema/sito.sql). I vettori sono una stima dai token, con il prezzo della Batch API."""
    esiste = lambda v: c.execute("SELECT to_regclass(%s) IS NOT NULL AS c", (v,)).fetchone()["c"]   # noqa: E731
    spesa = c.execute("""
        SELECT coalesce(sum(dollari) FILTER (WHERE giorno >= %s), 0)::float AS periodo,
               coalesce(sum(dollari) FILTER (WHERE giorno = current_date), 0)::float AS oggi,
               coalesce(sum(dollari), 0)::float AS sempre, min(giorno) AS dal
        FROM sito.spesa""", (dal,)).fetchone()
    per_giorno = {r["giorno"].isoformat(): {"api": float(r["d"])} for r in c.execute(
        "SELECT giorno, sum(dollari) AS d FROM sito.spesa WHERE giorno >= %s GROUP BY 1", (dal,))}
    chat, modelli, vettori = {}, [], {}
    if esiste("registro.uso_chat"):
        # solo le chat del sito (con conversazione) e i fascicoli; le prove dell'API restano fuori
        sito = "(conversazione IS NOT NULL OR modello = 'fascicolo')"
        chat = dict(c.execute(f"""
            SELECT count(*) AS domande, count(DISTINCT conversazione) AS conversazioni,
                   round(count(conversazione)::numeric / nullif(count(DISTINCT conversazione), 0), 1)::float AS turni_medi,
                   (percentile_cont(.5) WITHIN GROUP (ORDER BY ms) / 1000)::float AS secondi_mediana,
                   (percentile_cont(.9) WITHIN GROUP (ORDER BY ms) / 1000)::float AS secondi_p90,
                   count(*) FILTER (WHERE errore) AS errori, count(*) FILTER (WHERE lingua = 'en') AS inglese,
                   coalesce(sum(dollari), 0)::float AS dollari
            FROM registro.uso_chat WHERE creata >= %s AND {sito}""", (dal,)).fetchone())
        modelli = [dict(r) for r in c.execute(f"""
            SELECT CASE WHEN modello = 'fascicolo' THEN 'Fascicoli' ELSE 'Chat (' || modello || ')' END AS voce,
                   count(*) AS domande, round(sum(dollari)::numeric, 2)::float AS dollari,
                   round((avg(dollari) * 100)::numeric, 1)::float AS centesimi
            FROM registro.uso_chat WHERE creata >= %s AND {sito} GROUP BY 1 ORDER BY 3 DESC""", (dal,))]
    if esiste("registro.spesa_vettori"):
        prezzo = DOLLARI_PER_MILIONE / 1e6
        for r in c.execute("SELECT giorno, token FROM registro.spesa_vettori WHERE giorno >= %s", (dal,)):
            per_giorno.setdefault(r["giorno"].isoformat(), {})["vettori"] = float(r["token"]) * prezzo
        v = c.execute("""SELECT coalesce(sum(token) FILTER (WHERE giorno >= %s), 0) AS periodo, coalesce(sum(token), 0) AS sempre,
                                coalesce(sum(batch) FILTER (WHERE giorno >= %s), 0) AS batch, coalesce(sum(aperti), 0) AS aperti
                         FROM registro.spesa_vettori""", (dal, dal)).fetchone()
        vettori = {"modello": MODELLO_VETTORI, "token": int(v["periodo"]), "batch": int(v["batch"]), "aperti": int(v["aperti"]),
                   "dollari": float(v["periodo"]) * prezzo, "dollari_sempre": float(v["sempre"]) * prezzo}
    return {**dict(spesa), "tetto": float(env("AGENTE_DOLLARI_GIORNO", "25")), "chat": chat, "modelli": modelli,
            "vettori": vettori, "per_giorno": [{"giorno": k, **v} for k, v in sorted(per_giorno.items())]}


@router.get("/api/statistiche", include_in_schema=False)
def dati(req: Request, giorni: int = 30) -> dict:
    _login(req)
    giorni = max(1, min(giorni, GIORNI_TENUTI))
    dal = dt.date.today() - dt.timedelta(days=giorni - 1)
    with connessione_sito() as c:
        if c is None:
            raise HTTPException(503, "statistiche non configurate")
        per_giorno = c.execute("""
            SELECT giorno, count(DISTINCT visitatore) FILTER (WHERE evento = 'pagina') AS visitatori,
                   count(*) FILTER (WHERE evento = 'pagina') AS pagine,
                   count(*) FILTER (WHERE evento = 'domanda') AS domande, count(*) FILTER (WHERE evento = 'fascicolo') AS fascicoli
            FROM sito.visita WHERE giorno >= %s GROUP BY 1 ORDER BY 1""", (dal,)).fetchall()
        per_ora = c.execute("""
            SELECT to_char(date_trunc('hour', ts AT TIME ZONE 'Europe/Rome'), 'YYYY-MM-DD"T"HH24') AS ora,
                   count(DISTINCT visitatore) FILTER (WHERE evento = 'pagina') AS visitatori,
                   count(*) FILTER (WHERE evento = 'pagina') AS pagine,
                   count(*) FILTER (WHERE evento = 'domanda') AS domande, count(*) FILTER (WHERE evento = 'fascicolo') AS fascicoli,
                   count(DISTINCT visitatore) FILTER (WHERE evento = 'pagina' AND lingua IS DISTINCT FROM 'it') AS altre_lingue
            FROM sito.visita WHERE ts >= now() - interval '24 hours' GROUP BY 1 ORDER BY 1""").fetchall()
        adesso = c.execute("SELECT to_char(now() AT TIME ZONE 'Europe/Rome', 'YYYY-MM-DD\"T\"HH24') AS adesso").fetchone()["adesso"]
        totali = c.execute("""
            SELECT count(DISTINCT (giorno, visitatore)) FILTER (WHERE evento = 'pagina') AS visitatori,
                   count(*) FILTER (WHERE evento = 'pagina') AS pagine,
                   count(*) FILTER (WHERE evento = 'domanda') AS domande, count(*) FILTER (WHERE evento = 'fascicolo') AS fascicoli
            FROM sito.visita WHERE giorno >= %s""", (dal,)).fetchone()

        def classifica(colonna: str, n: int = 12, filtro: str = "true") -> list[dict]:
            return [dict(r) for r in c.execute(f"""
                SELECT coalesce({colonna}, 'non indicato') AS voce, count(DISTINCT (giorno, visitatore)) AS visitatori,
                       count(*) AS pagine
                FROM sito.visita WHERE giorno >= %s AND evento = 'pagina' AND {filtro}
                GROUP BY 1 ORDER BY 2 DESC, 3 DESC LIMIT {n}""", (dal,))]

        # percorsi: la pagina vista per ultima prima di ogni domanda alla chat, e l'ultima pagina del giorno di ogni visitatore
        arrivi_chat = [dict(r) for r in c.execute("""
            SELECT coalesce(p.percorso, 'nessuna pagina prima') AS voce, count(DISTINCT (d.giorno, d.visitatore)) AS visitatori,
                   count(*) AS domande
            FROM sito.visita d LEFT JOIN LATERAL (
              SELECT percorso FROM sito.visita p WHERE p.visitatore = d.visitatore AND p.giorno = d.giorno AND p.evento = 'pagina'
                AND p.ts <= d.ts ORDER BY p.ts DESC LIMIT 1) p ON true
            WHERE d.giorno >= %s AND d.evento = 'domanda' GROUP BY 1 ORDER BY 3 DESC LIMIT 10""", (dal,))]
        uscite = [dict(r) for r in c.execute("""
            SELECT coalesce(percorso, 'non indicato') AS voce, count(*) AS visitatori FROM (
              SELECT DISTINCT ON (giorno, visitatore) percorso FROM sito.visita WHERE giorno >= %s AND evento = 'pagina'
              ORDER BY giorno, visitatore, ts DESC) u
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10""", (dal,))]
        # strumenti e ricerche della chat: la vista registro.uso_strumenti (schema/sito.sql), senza domande né risposte
        strumenti, ricerche = [], []
        if c.execute("SELECT to_regclass('registro.uso_strumenti') IS NOT NULL AS c").fetchone()["c"]:
            strumenti = [dict(r) for r in c.execute("""
                SELECT strumento AS voce, count(*) AS chiamate FROM registro.uso_strumenti
                WHERE creata >= %s GROUP BY 1 ORDER BY 2 DESC LIMIT 15""", (dal,))]
            ricerche = [dict(r) for r in c.execute("""
                SELECT lower(ricerca) AS voce, count(*) AS chiamate FROM registro.uso_strumenti
                WHERE creata >= %s AND ricerca IS NOT NULL AND ricerca <> '' GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 20""", (dal,))]
        costi = _costi(c, dal)
        return {"dal": dal, "al": dt.date.today(), "giorni": giorni, "totali": dict(totali), "costi": costi,
                "per_giorno": [dict(r) for r in per_giorno],
                "per_ora": [dict(r) for r in per_ora], "adesso": adesso, "attivi": attivi_ora(), "pagine": classifica("percorso", 15),
                "provenienze": classifica("provenienza"), "dispositivi": classifica("dispositivo"),
                "browser": classifica("browser"), "lingue": classifica("lingua"),
                "paesi": classifica("paese"), "regioni": classifica("regione", 20, "paese = 'IT'"),
                "arrivi_chat": arrivi_chat, "uscite": uscite, "strumenti": strumenti, "ricerche": ricerche}
