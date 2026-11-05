"""Pannello del responsabile del sistema: /sistema e i suoi dati (/api/sistema), dietro lo stesso login delle statistiche.

Tre fonti: dati/sistema/stato.json, che il cron della VPS riscrive ogni 10 minuti (`python -m pipeline sistema`: giri,
quarantena, disco, memoria, container, backup, versione); Postgres con l'utente `lettura` (quanto sono freschi i dati,
quante righe, batch dei vettori); lo schema `sito` per spesa e chat (registro.uso_chat, senza domande né risposte).
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import psycopg
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from pipeline.ambiente import env

from . import statistiche
from .db import connessione, connessione_sito

router = APIRouter()
PAGINA = Path(__file__).parent / "sistema.html"
STATO = Path(env("SISTEMA_FILE", "dati/sistema/stato.json"))
TABELLE = ("person", "sitting", "agenda_item", "speech", "vote", "ballot", "act", "act_text", "amendment", "document",
           "reaction", "video", "passage", "passage_vector")


def _stato() -> dict:
    try:
        d = json.loads(STATO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"mancante": True}
    d["eta_minuti"] = round((time.time() - d.get("scritto", 0)) / 60)
    return d


def _dati() -> dict:
    """Freschezza e dimensioni del v3: date massime per ramo e conteggi stimati dal catalogo (veloci, non esatti)."""
    try:
        with connessione() as c:
            sedute = [dict(r) for r in c.execute("""
                SELECT chamber AS ramo, kind AS tipo, max(date) FILTER (WHERE status = 'held') AS ultima_tenuta,
                       max(date) FILTER (WHERE status = 'planned') AS prossima, count(*) AS sedute
                FROM sitting GROUP BY 1, 2 ORDER BY 1, 2""")]
            voti = [dict(r) for r in c.execute("""
                SELECT chamber AS ramo, max(date) AS ultima, count(*) FILTER (WHERE date >= current_date - 30) AS ultimi_30_giorni
                FROM vote GROUP BY 1 ORDER BY 1""")]
            atti = [dict(r) for r in c.execute("""
                SELECT chamber AS ramo, max(date) AS ultimo_presentato, max(status_date) AS ultimo_cambio, max(law_date) FILTER (WHERE law_date <= current_date) AS ultima_legge
                FROM act GROUP BY 1 ORDER BY 1""")]
            caricato = c.execute("SELECT max(loaded_at) AS t FROM sitting").fetchone()["t"]
            righe = {r["t"]: int(r["n"]) for r in c.execute(
                "SELECT relname AS t, greatest(reltuples, 0)::bigint AS n FROM pg_class WHERE relkind = 'r' AND relname = ANY(%s)",
                (list(TABELLE),))}
            peso = c.execute("SELECT pg_database_size(current_database()) AS b").fetchone()["b"]
            vettori = dict(c.execute("""
                SELECT count(*) FILTER (WHERE status <> 'completed') AS aperti, count(*) FILTER (WHERE error IS NOT NULL) AS con_errore,
                       max(sent_at) AS ultimo_invio, max(collected_at) AS ultima_raccolta FROM vector_batch""").fetchone())
    except psycopg.Error as e:
        return {"errore": type(e).__name__}
    return {"sedute": sedute, "voti": voti, "atti": atti, "caricato": caricato, "righe": righe, "peso": peso, "vettori": vettori}


def _chat(c: psycopg.Connection, dal: dt.date, al: dt.date) -> dict:
    """Errori e tempi della chat nel periodo, dalla vista registro.uso_chat."""
    if not c.execute("SELECT to_regclass('registro.uso_chat') IS NOT NULL AS c").fetchone()["c"]:
        return {}
    filtro = f"(conversazione IS NOT NULL OR modello = 'fascicolo') AND {statistiche.ROMA} BETWEEN %(dal)s AND %(al)s"
    p = {"dal": dal, "al": al}
    per_giorno = [dict(r) for r in c.execute(f"""
        SELECT (creata AT TIME ZONE 'Europe/Rome')::date AS giorno, count(*) AS domande, count(*) FILTER (WHERE errore) AS errori,
               round((percentile_cont(.5) WITHIN GROUP (ORDER BY ms) / 1000)::numeric, 1)::float AS mediana,
               round((percentile_cont(.9) WITHIN GROUP (ORDER BY ms) / 1000)::numeric, 1)::float AS p90,
               round(sum(dollari)::numeric, 2)::float AS dollari
        FROM registro.uso_chat WHERE {filtro} GROUP BY 1 ORDER BY 1""", p)]
    errori = [dict(r) for r in c.execute(f"""
        SELECT creata, modello, ms, errore_testo FROM registro.uso_chat
        WHERE errore AND {filtro} ORDER BY creata DESC LIMIT 30""", p)]
    lente = c.execute(f"""SELECT count(*) AS n FROM registro.uso_chat
        WHERE ms > 120000 AND {filtro}""", p).fetchone()["n"]
    return {"per_giorno": per_giorno, "errori": errori, "oltre_2_minuti": lente}


@router.get("/sistema", response_class=HTMLResponse, include_in_schema=False)
def pannello(req: Request) -> HTMLResponse:
    statistiche._login(req, pagina=True)
    return HTMLResponse(PAGINA.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@router.get("/api/sistema", include_in_schema=False)
def dati(req: Request, giorni: int = 14, dal: dt.date | None = None, al: dt.date | None = None) -> dict:
    statistiche._login(req)
    dal, al = statistiche.periodo(giorni, dal, al)
    sito, chat = {}, {}
    with connessione_sito() as c:
        if c is not None:
            sito = statistiche._costi(c, dal, al)
            chat = _chat(c, dal, al)
            sito["oggi_domande"] = c.execute("SELECT count(*) AS n FROM sito.visita WHERE giorno = current_date AND evento = 'domanda'").fetchone()["n"]
    return {"adesso": time.time(), "dal": dal, "al": al, "macchina": _stato(), "dati": _dati(), "costi": sito, "chat": chat,
            "limiti": {"domande_ora": int(env("AGENTE_DOMANDE_ORA", "10")), "dollari_giorno": float(env("AGENTE_DOLLARI_GIORNO", "25"))}}
