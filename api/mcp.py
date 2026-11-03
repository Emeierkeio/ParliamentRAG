"""Server MCP pubblico, in sola lettura: JSON-RPC su HTTP (POST /mcp, Streamable HTTP senza stato). Espone gli otto
strumenti del server di produzione (pubblico.py), con gli stessi nomi e argomenti, così i client già collegati a
mcp.parliamentrag.it continuano a funzionare. I dodici strumenti italiani del registro (quelli dell'agente) si vedono e
si chiamano anche qui solo con MCP_STRUMENTI_INTERNI=1."""

from __future__ import annotations

import json
from typing import Any

import psycopg
from pydantic import ValidationError

from pipeline.ambiente import env

from . import pubblico, registro

VERSIONI = ("2025-06-18", "2025-03-26", "2024-11-05")       # la prima è la più recente
VERSIONE_SERVER = "3.0.0"

ISTRUZIONI = (
    "Tools over official Italian Parliament data, Chamber of Deputies and Senate (19th legislature, via parliamentrag.it). "
    "Tools take a `chamber` argument where it matters: \"camera\", \"senato\" or \"both\"; votes are never summed across "
    "the two houses. Data is in Italian. Speeches of the Chamber and acts link back to the official record: cite those "
    "links when reporting facts. When you report the results of a specific roll-call vote, you can call "
    "get_vote_hemicycle for that vote_id: it returns the official totals and the per-group breakdown (no chart is drawn: "
    "report the numbers in words or in a table). For secret ballots it returns an explanation instead. Always answer in "
    "the language of the conversation (Italian, English, ...): translate summaries and labels, but keep verbatim quotes in "
    "the original Italian. If a call times out, retry once. ParliamentRAG makes three guarantees on answers about "
    "Parliament: all groups are heard, the voices quoted are authoritative on the topic, and every quote is exact, with a "
    "link to the record. Whenever your answer reports or quotes what deputies or senators said, put quotes in «…» with the "
    "speaker's name nearby, then call verify_answer on the final answer and the user's question. Do not rewrite the "
    "answer to make the checks pass: show the outcome. End the answer with the three lines of `verdict` from the result, "
    "translated into the language of the conversation, keeping the ✅/❌ marks and the facts as given, and the closing "
    "line about ParliamentRAG with its link.\n")

INFO = {"name": "ParliamentRAG", "version": VERSIONE_SERVER, "websiteUrl": "https://www.parliamentrag.it",
        "icons": [{"src": "https://mcp.parliamentrag.it/icon.png", "mimeType": "image/png", "sizes": ["512x512"]}]}
CAPACITA = {"experimental": {}, "prompts": {"listChanged": False}, "resources": {"subscribe": False, "listChanged": False},
            "tools": {"listChanged": False}}


def interni() -> bool:
    return env("MCP_STRUMENTI_INTERNI", "0") == "1"


def _errore(ident, codice: int, messaggio: str) -> dict:
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": codice, "message": messaggio}}


def _esito(ident, testo: str, errore: bool = False, strutturato: Any = None) -> dict:
    r: dict = {"content": [{"type": "text", "text": testo}], "isError": errore}
    if strutturato is not None:
        r["structuredContent"] = strutturato
    return {"jsonrpc": "2.0", "id": ident, "result": r}


def versione(chiesta: Any) -> str:
    """La versione del protocollo chiesta dal client, se la conosciamo; se no la più recente."""
    return chiesta if chiesta in VERSIONI else VERSIONI[0]


def strumenti() -> list[dict]:
    lista = [{"name": s.nome, "title": pubblico.TITOLI[s.nome], "description": s.descrizione, "inputSchema": s.schema(),
              "annotations": {"title": pubblico.TITOLI[s.nome], "readOnlyHint": True, "destructiveHint": False,
                              "idempotentHint": True, "openWorldHint": True}} for s in pubblico.STRUMENTI]
    if interni():
        lista += [{"name": s.nome, "description": s.descrizione, "inputSchema": s.schema(), "annotations": {"readOnlyHint": True}}
                  for s in registro.STRUMENTI]
    return lista


def serve_db(msg: Any) -> bool:
    """Solo tools/call legge il database: initialize, tools/list e ping rispondono anche col database spento."""
    return isinstance(msg, dict) and msg.get("method") == "tools/call"


def _chiama(c: psycopg.Connection, ident, nome: Any, argomenti: Any) -> dict:
    if not isinstance(argomenti, dict):
        return _esito(ident, "argomenti non validi: serve un oggetto", errore=True)
    pubblici, interno = nome in pubblico.PER_NOME, interni() and nome in registro.PER_NOME
    if not (pubblici or interno):
        return _errore(ident, -32602, f"strumento sconosciuto: {nome}")
    try:
        if pubblici:
            ris = pubblico.esegui(c, nome, argomenti)
            testo = json.dumps(ris, ensure_ascii=False, indent=2, default=str)
            # l'oggetto va com'è in structuredContent (la produzione dà oggetti); una lista finirebbe in {"result": …}
            return _esito(ident, testo, strutturato=json.loads(testo) if isinstance(ris, dict) else {"result": json.loads(testo)})
        ris = registro.esegui(c, nome, argomenti)
        return _esito(ident, registro.in_testo(ris), strutturato={"result": ris})
    except ValidationError as e:
        return _esito(ident, f"argomenti non validi: {e.errors(include_url=False)}", errore=True)
    except pubblico.NonTrovato as e:
        return _esito(ident, str(e), errore=True)
    except psycopg.errors.QueryCanceled:
        return _esito(ident, "richiesta troppo lunga: restringi la ricerca", errore=True)


def gestisci(c: psycopg.Connection | None, msg: Any) -> dict | None:
    """Un messaggio JSON-RPC. None per notifiche e risposte del client (all'HTTP: 202 senza corpo)."""
    if isinstance(msg, list):
        return _errore(None, -32600, "richieste in blocco (batch) non supportate: un messaggio per richiesta")
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _errore(None, -32600, "richiesta non valida")
    if "method" not in msg:                              # risposta del client a una nostra richiesta: non ne facciamo
        return None
    if not isinstance(msg["method"], str):
        return _errore(msg.get("id"), -32600, "richiesta non valida")
    ident, metodo, p = msg.get("id"), msg["method"], msg.get("params") or {}
    if "id" not in msg or ident is None:                 # notifiche (notifications/initialized…): nessuna risposta
        return None
    if not isinstance(p, dict):
        return _errore(ident, -32602, "params deve essere un oggetto")
    if metodo == "initialize":
        return {"jsonrpc": "2.0", "id": ident, "result": {
            "protocolVersion": versione(p.get("protocolVersion")), "capabilities": CAPACITA, "serverInfo": INFO,
            "instructions": ISTRUZIONI}}
    if metodo == "ping":
        return {"jsonrpc": "2.0", "id": ident, "result": {}}
    if metodo == "tools/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"tools": strumenti()}}
    if metodo == "resources/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"resources": []}}
    if metodo == "resources/templates/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"resourceTemplates": []}}
    if metodo == "prompts/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"prompts": []}}
    if metodo == "tools/call":
        return _chiama(c, ident, p.get("name"), p.get("arguments") or {})
    return _errore(ident, -32601, f"metodo sconosciuto: {metodo}")
