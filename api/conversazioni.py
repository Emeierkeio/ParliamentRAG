"""Registro delle chat (schema/registro.sql): una riga per domanda, con risposta, strumenti, tempi e costo, senza IP.
Scrive con l'utente `registro`, che può solo inserire. Se il registro non è configurato o non risponde, la chat
funziona lo stesso: si perde solo la riga."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator

import psycopg

from pipeline.ambiente import env

log = logging.getLogger("parliamentrag.conversazioni")


def _password() -> str | None:
    try:
        return env("REGISTRO_PG_PASSWORD")
    except KeyError:
        return None


def salva(riga: dict) -> None:
    password = _password()
    if not password:
        return
    try:
        with psycopg.connect(host=env("API_PG_HOST", "localhost"), port=int(env("PG_PORTA", "5440")), dbname="parliamentrag",
                             user="registro", password=password, application_name="parliamentrag-registro",
                             autocommit=True, connect_timeout=5) as c:
            c.execute("""INSERT INTO registro.chat (conversazione, turno, lingua, domanda, risposta, strumenti, errore, ms, dollari, modello)
                         VALUES (%(conversazione)s, %(turno)s, %(lingua)s, %(domanda)s, %(risposta)s, %(strumenti)s, %(errore)s,
                                 %(ms)s, %(dollari)s, %(modello)s)""", {**riga, "strumenti": json.dumps(riga["strumenti"], ensure_ascii=False)})
    except psycopg.Error as e:
        log.warning("registro delle chat non scritto: %s", type(e).__name__)


def registra(eventi: Iterator[dict], domanda: str, lingua: str, conversazione: str | None, turno: int | None,
             misure: dict) -> Iterator[dict]:
    """Passa gli eventi dell'agente così come sono e, alla fine, scrive la riga. Anche se il client chiude prima."""
    inizio, risposta, strumenti, errori = time.monotonic(), [], [], []
    try:
        for e in eventi:
            t = e.get("type")
            if t == "delta":
                risposta.append(e.get("text") or "")
            elif t == "tool" and e.get("state") == "start":
                strumenti.append({"nome": e.get("name"), "argomenti": e.get("args"), "risultati": None})
            elif t == "tool" and e.get("state") == "done" and strumenti:
                strumenti[-1]["risultati"] = e.get("count")
            elif t == "error":
                errori.append(e.get("text") or "")
            yield e
    finally:
        getattr(eventi, "close", lambda: None)()   # chiude prima l'agente, che così lascia la spesa in `misure`
        salva({"conversazione": conversazione, "turno": turno, "lingua": lingua, "domanda": domanda,
               "risposta": "".join(risposta) or None, "strumenti": strumenti, "errore": "; ".join(errori) or None,
               "ms": int((time.monotonic() - inizio) * 1000), "dollari": round(misure.get("dollari", 0.0), 5),
               "modello": misure.get("modello")})
