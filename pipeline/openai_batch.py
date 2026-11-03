"""Batch API di OpenAI con la sola libreria standard: carica un file di richieste, crea il lavoro, scarica i risultati.

La chiave sta in OPENAI_API_KEY (ambiente o .env) e non si stampa.
"""

import json
import time
import urllib.request
import uuid
from pathlib import Path

from pipeline.ambiente import env

BASE = "https://api.openai.com/v1"


def _chiama(metodo: str, percorso: str, corpo: bytes | None = None, tipo: str = "application/json") -> bytes:
    req = urllib.request.Request(BASE + percorso, corpo, method=metodo,
                                 headers={"Authorization": "Bearer " + env("OPENAI_API_KEY"), "Content-Type": tipo})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def invia(richieste: Path, endpoint: str, descrizione: str) -> str:
    """Carica il file JSONL e crea il lavoro; restituisce l'id del batch."""
    confine = uuid.uuid4().hex
    corpo = (f"--{confine}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\nbatch\r\n"
             f"--{confine}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{richieste.name}\"\r\n"
             "Content-Type: application/jsonl\r\n\r\n").encode() + richieste.read_bytes() + f"\r\n--{confine}--\r\n".encode()
    file_id = json.loads(_chiama("POST", "/files", corpo, f"multipart/form-data; boundary={confine}"))["id"]
    lavoro = json.loads(_chiama("POST", "/batches", json.dumps({
        "input_file_id": file_id, "endpoint": endpoint, "completion_window": "24h",
        "metadata": {"descrizione": descrizione}}).encode()))
    return lavoro["id"]


def stato(batch_id: str) -> dict:
    return json.loads(_chiama("GET", f"/batches/{batch_id}"))


def aspetta(batch_id: str, ogni: int = 60) -> dict:
    while True:
        s = stato(batch_id)
        if s["status"] in ("completed", "failed", "expired", "cancelled"):
            return s
        time.sleep(ogni)


def risultati(s: dict) -> dict[str, dict]:
    """custom_id -> corpo della risposta, dai file di uscita e di errore del batch."""
    fuori = {}
    for chiave in ("output_file_id", "error_file_id"):
        if s.get(chiave):
            for riga in _chiama("GET", f"/files/{s[chiave]}/content").decode().splitlines():
                r = json.loads(riga)
                fuori[r["custom_id"]] = (r.get("response") or {}).get("body") or {"errore": r.get("error")}
    return fuori
