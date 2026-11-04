"""Statistiche di visita fatte da noi, senza cookie e senza salvare l'IP (schema/sito.sql, tabella sito.visita).

La pagina manda a POST /api/visita il percorso, la provenienza, la larghezza della finestra e la lingua; il servizio
aggiunge le domande alla chat e i fascicoli (registra). Il visitatore è un'impronta di IP, browser e giorno con la
chiave LIMITE_SALE: conta i visitatori unici del giorno e non si ricollega ai giorni dopo. Il pannello /statistiche e i
suoi dati (/api/statistiche) stanno dietro un login (STATISTICHE_UTENTE, STATISTICHE_PASSWORD); senza, non esistono.
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
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from pipeline.ambiente import env

from . import agente
from .db import connessione_sito
from .rete import ip

router = APIRouter()
log = logging.getLogger("parliamentrag.statistiche")
PAGINA = Path(__file__).parent / "statistiche.html"
NOSTRI = ("parliamentrag.it", "www.parliamentrag.it", "mcp.parliamentrag.it")
ROBOT = re.compile(r"bot|crawl|spider|slurp|headless|preview|monitor|curl|wget|python|httpx|go-http|scrapy", re.I)
GIORNI_TENUTI = 400


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
        c.execute("""INSERT INTO sito.visita (giorno, evento, percorso, provenienza, dispositivo, browser, lingua, visitatore)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                  (oggi, evento, p, provenienza(r), dispositivo(w), browser(ua), (lingua or "")[:2].lower() or None,
                   _visitatore(ip(req), ua, oggi)))
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
    return HTMLResponse(PAGINA.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


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
        totali = c.execute("""
            SELECT count(DISTINCT (giorno, visitatore)) FILTER (WHERE evento = 'pagina') AS visitatori,
                   count(*) FILTER (WHERE evento = 'pagina') AS pagine,
                   count(*) FILTER (WHERE evento = 'domanda') AS domande, count(*) FILTER (WHERE evento = 'fascicolo') AS fascicoli
            FROM sito.visita WHERE giorno >= %s""", (dal,)).fetchone()

        def classifica(colonna: str, n: int = 12) -> list[dict]:
            return [dict(r) for r in c.execute(f"""
                SELECT coalesce({colonna}, 'non indicato') AS voce, count(DISTINCT (giorno, visitatore)) AS visitatori,
                       count(*) AS pagine
                FROM sito.visita WHERE giorno >= %s AND evento = 'pagina' GROUP BY 1 ORDER BY 2 DESC, 3 DESC LIMIT {n}""", (dal,))]
        return {"dal": dal, "al": dt.date.today(), "giorni": giorni, "totali": dict(totali),
                "per_giorno": [dict(r) for r in per_giorno], "pagine": classifica("percorso", 15),
                "provenienze": classifica("provenienza"), "dispositivi": classifica("dispositivo"),
                "browser": classifica("browser"), "lingue": classifica("lingua")}
