"""Rotte HTTP del servizio: i dati in lettura e la chat sotto /v1, il server MCP su /mcp, il sito (pagine in `sito/`,
rotte /api e /dati in sito.py e nei moduli sito_*). Ogni rotta dei dati chiama uno strumento di `strumenti/`; nessuna
rotta accetta query libere. Avvio in locale: `.venv/bin/uvicorn api.main:app --port 8790`."""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Literal

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import modelli as M
from pipeline.ambiente import QUI

from . import agente, mcp, sito, sito_emendamenti, sito_parlamentari
from .db import connessione, per_richiesta
from .rete import ip as _ip
from .strumenti import atti, persone, ricerca, sedute, voti

Ramo = Literal["camera", "senato"]
Db = Annotated[psycopg.Connection, Depends(per_richiesta)]
Limite = Annotated[int, Query(ge=1, le=200)]
Scarto = Annotated[int, Query(ge=0, le=100_000)]

app = FastAPI(title="ParliamentRAG API", version="0.1.0", docs_url="/v1/docs", openapi_url="/v1/openapi.json", redoc_url=None,
              description="Dati ufficiali del Parlamento italiano (XIX legislatura) in sola lettura.")

# Limite per IP: finestra scorrevole in memoria, per processo. Vale per le API e, più largo, per i dati del sito; le
# pagine e i loro file non hanno limite: una pagina sola ne carica decine. Le domande alla chat hanno il loro limite.
RICHIESTE_PER_MINUTO = {"api": 120, "dati": 600}
_finestre: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _classe(percorso: str) -> str | None:
    if percorso.startswith(("/v1/", "/mcp", "/api/")):
        return "api"
    return "dati" if percorso.startswith("/dati/") else None


@app.middleware("http")
async def limite_per_ip(req: Request, chiama):
    classe = _classe(req.url.path)
    if classe is None:
        return await chiama(req)
    ora, chiave = time.monotonic(), (classe, _ip(req))
    if len(_finestre) > 50_000:                      # niente crescita senza fine: via gli IP fermi da più di un minuto
        for k in [k for k, f in _finestre.items() if not f or ora - f[-1] > 60]:
            del _finestre[k]
    f = _finestre[chiave]
    while f and ora - f[0] > 60:
        f.popleft()
    if len(f) >= RICHIESTE_PER_MINUTO[classe]:
        return JSONResponse({"detail": "troppe richieste: riprova fra un minuto"}, status_code=429, headers={"Retry-After": "60"})
    f.append(ora)
    return await chiama(req)


@app.exception_handler(psycopg.errors.QueryCanceled)
async def troppo_lunga(_req: Request, _e: Exception):
    return JSONResponse({"detail": "la richiesta ha impiegato troppo: restringi la ricerca"}, status_code=503)


def _o_404(x, messaggio: str):
    if x is None:
        raise HTTPException(404, messaggio)
    return x


@app.get("/v1/salute")
def salute(c: Db) -> dict:
    r = c.execute("SELECT max(date) AS ultima FROM sitting WHERE status = 'held'").fetchone()
    return {"ok": True, "ultima_seduta": r["ultima"]}


@app.get("/v1/persone", response_model=list[M.PersonBrief])
def cerca_persone(c: Db, q: str | None = None, chamber: Ramo | None = None, group: str | None = None,
                  in_office: bool | None = True, limit: Limite = 50):
    return persone.cerca_persone(c, q, chamber, group, in_office, limit)


@app.get("/v1/persone/{uri}", response_model=M.Person)
def scheda_persona(c: Db, uri: str):
    return _o_404(persone.scheda_persona(c, uri), "persona non trovata")


@app.get("/v1/composizione/{chamber}", response_model=M.Composition)
def composizione(c: Db, chamber: Ramo, date: dt.date | None = None):
    return persone.composizione(c, chamber, date)


@app.get("/v1/sedute", response_model=M.Page[M.SittingBrief])
def elenco_sedute(c: Db, chamber: Ramo | None = None, body: str | None = None, start: dt.date | None = None,
                  end: dt.date | None = None, limit: Limite = 50, offset: Scarto = 0):
    n, xs = sedute.elenco_sedute(c, chamber, body, start, end, limit, offset)
    return M.Page[M.SittingBrief](total=n, offset=offset, items=xs)


@app.get("/v1/sedute/{uri}", response_model=M.Sitting)
def seduta(c: Db, uri: str):
    return _o_404(sedute.seduta(c, uri), "seduta non trovata")


@app.get("/v1/votazioni", response_model=M.Page[M.VoteBrief])
def elenco_votazioni(c: Db, chamber: Ramo | None = None, act: str | None = None, kind: str | None = None,
                     start: dt.date | None = None, end: dt.date | None = None, final: bool | None = None,
                     limit: Limite = 50, offset: Scarto = 0):
    n, xs = voti.elenco_votazioni(c, chamber, act, kind, start, end, final, limit, offset)
    return M.Page[M.VoteBrief](total=n, offset=offset, items=xs)


@app.get("/v1/votazioni/{uri}", response_model=M.Vote)
def votazione(c: Db, uri: str, ballots: bool = True):
    return _o_404(voti.votazione(c, uri, ballots), "votazione non trovata")


@app.get("/v1/atti", response_model=M.Page[M.ActBrief])
def cerca_atti(c: Db, q: str | None = None, chamber: Ramo | None = None, kind: str | None = None, number: str | None = None,
               signer: str | None = None, limit: Limite = 50, offset: Scarto = 0):
    n, xs = atti.cerca_atti(c, q, chamber, kind, number, signer, limit, offset)
    return M.Page[M.ActBrief](total=n, offset=offset, items=xs)


@app.get("/v1/atti/{uri}", response_model=M.Act)
def atto(c: Db, uri: str):
    return _o_404(atti.atto(c, uri), "atto non trovato")


@app.get("/v1/atti/{uri}/emendamenti", response_model=M.Page[M.Amendment])
def emendamenti(c: Db, uri: str, signer: str | None = None, group: str | None = None, outcome: str | None = None,
                venue: str | None = None, q: str | None = None, limit: Limite = 50, offset: Scarto = 0):
    n, xs = atti.emendamenti(c, uri, signer, group, outcome, venue, q, limit, offset)
    return M.Page[M.Amendment](total=n, offset=offset, items=xs)


@app.get("/v1/interventi", response_model=list[M.SpeechHit])
def cerca_interventi(c: Db, q: Annotated[str, Query(min_length=2, max_length=200)], chamber: Ramo | None = None,
                     person: str | None = None, start: dt.date | None = None, end: dt.date | None = None,
                     include_summaries: bool = True, limit: Annotated[int, Query(ge=1, le=50)] = 20, offset: Scarto = 0):
    return ricerca.cerca_interventi(c, q, chamber, person, start, end, include_summaries, limit, offset)


@app.get("/v1/uso")
def uso_chat(req: Request) -> dict:
    """Domande alla chat usate nell'ora in corso da questo indirizzo, limite e secondi alla ripartenza del conteggio."""
    return agente.uso(_ip(req))


@app.post("/v1/chat")
def chat(req: Request, d: sito.Domanda):
    """Risposta dell'agente in NDJSON: un evento per riga."""
    return sito.risposta_ndjson(_ip(req), d)


# CORS solo per /mcp, perché i client MCP nel browser (ispettori, app web) leggano le risposte e l'mcp-session-id
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization, Mcp-Session-Id, Mcp-Protocol-Version, Last-Event-ID",
        "Access-Control-Expose-Headers": "Mcp-Session-Id", "Access-Control-Max-Age": "86400"}


@app.middleware("http")
async def cors_mcp(req: Request, chiama):
    if req.url.path != "/mcp":
        return await chiama(req)
    risposta = Response(status_code=204) if req.method == "OPTIONS" else await chiama(req)
    risposta.headers.update(CORS)
    return risposta


def _mcp_risposta(req: Request, corpo: dict, stato: int = 200, intestazioni: dict | None = None) -> Response:
    """Come la produzione: in SSE (un solo evento «message») se il client accetta text/event-stream, se no in JSON."""
    if "text/event-stream" in req.headers.get("accept", ""):
        testo = "event: message\ndata: " + json.dumps(corpo, ensure_ascii=False, default=str) + "\n\n"
        return Response(testo, status_code=stato, media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache, no-transform", **(intestazioni or {})})
    return JSONResponse(corpo, status_code=stato, headers=intestazioni)


def _mcp_esegui(msg):
    if not mcp.serve_db(msg):
        return mcp.gestisci(None, msg)
    with connessione() as c:
        return mcp.gestisci(c, msg)


@app.post("/mcp")
async def server_mcp(req: Request):
    try:
        msg = json.loads(await req.body())
    except ValueError:
        return _mcp_risposta(req, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON non valido"}}, 400)
    # fuori dal ciclo degli eventi: le query lunghe non fermano le altre richieste
    risposta = await run_in_threadpool(_mcp_esegui, msg)
    if risposta is None:
        return Response(status_code=202)
    if isinstance(msg, list) or (risposta.get("id") is None and "error" in risposta):
        return _mcp_risposta(req, risposta, 400)
    # senza stato: l'id di sessione serve ai client che lo aspettano, il server non lo legge
    sessione = {"Mcp-Session-Id": uuid.uuid4().hex} if isinstance(msg, dict) and msg.get("method") == "initialize" else None
    return _mcp_risposta(req, risposta, 200, sessione)


@app.api_route("/mcp", methods=["GET", "DELETE"])
def mcp_altri_metodi():
    """Niente flusso SSE dal server né sessioni da chiudere: solo POST."""
    return Response(status_code=405, headers={"Allow": "POST"})


ICONA = Path(__file__).with_name("icona.png")


@app.get("/icon.png", include_in_schema=False)
def icona():
    """L'icona dichiarata in serverInfo.icons (https://mcp.parliamentrag.it/icon.png)."""
    return Response(ICONA.read_bytes(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.middleware("http")
async def pagine_sempre_fresche(req: Request, chiama):
    """Le pagine e i loro file si riconvalidano a ogni visita (ETag): dopo un aggiornamento nessuno resta sul vecchio."""
    risposta = await chiama(req)
    if not req.url.path.startswith(("/v1/", "/mcp", "/api/")):
        risposta.headers.setdefault("Cache-Control", "no-cache")
    return risposta


@app.on_event("startup")
def scalda_schede() -> None:
    """Indice dei deputati ed elenco dei senatori pronti prima del primo visitatore, e ricalcolati in tempo."""
    threading.Thread(target=sito_parlamentari.scalda, name="scalda-schede", daemon=True).start()

    def leggi() -> None:                              # l'elenco delle leggi con gli emendamenti: 2-4 s a freddo
        try:
            with connessione() as c:
                sito_emendamenti.elenco(c)
        except Exception as e:                       # noqa: BLE001 — lo calcola il primo visitatore
            logging.getLogger("parliamentrag.sito").warning("elenco delle leggi non preparato: %s", type(e).__name__)
    threading.Thread(target=leggi, name="scalda-leggi", daemon=True).start()


app.include_router(sito.router)
app.include_router(sito_parlamentari.router)
app.include_router(sito_emendamenti.router)
# le pagine per ultime: le rotte sopra hanno la precedenza
app.mount("/", StaticFiles(directory=QUI / "sito", html=True), name="sito")
