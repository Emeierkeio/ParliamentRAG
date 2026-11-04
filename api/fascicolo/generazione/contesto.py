"""Lo stato di un fascicolo mentre si scrive: rami della domanda, IP (per la spesa), voti finali dei gruppi. Variabili di
contesto, così due fascicoli in parallelo non si mescolano; `in_parallelo` le passa ai thread.

Le chiamate al modello passano da modello.py: `chat` col modello e l'IP del fascicolo, `vettori_piccoli` per i
confronti fra testi brevi (text-embedding-3-small, come prima: le soglie sono tarate su quello)."""

from __future__ import annotations

import contextvars
import math
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from typing import Any

from .. import modello
from .impostazioni import MODELLO_VETTORI_PICCOLI

RAMI: ContextVar[tuple[str, ...] | None] = ContextVar("fascicolo_rami", default=None)
IP: ContextVar[str | None] = ContextVar("fascicolo_ip", default=None)
VOTI_GRUPPI: ContextVar[dict[str, str]] = ContextVar("fascicolo_voti_gruppi", default={})
TUTTI_I_RAMI = ("camera", "senato")
PARALLELI = 12                     # chiamate al modello insieme, come le sezioni scritte in parallelo di prima


def rami() -> tuple[str, ...]:
    return RAMI.get() or TUTTI_I_RAMI


def in_parallelo(*funzioni: Callable[[], Any]) -> list[Any]:
    """Esegue le funzioni in thread, ognuna nel contesto di chi chiama; i risultati nell'ordine dato."""
    if len(funzioni) <= 1:
        return [f() for f in funzioni]
    with ThreadPoolExecutor(max_workers=min(PARALLELI, len(funzioni))) as pool:
        futuri = [pool.submit(contextvars.copy_context().run, f) for f in funzioni]
        return [f.result() for f in futuri]


def chat(modello_: str, messaggi: list[dict], **altro) -> str:
    """Una risposta del modello, con la spesa sull'IP del fascicolo. `massimo` è max_completion_tokens."""
    return modello.chat(modello_, messaggi, IP.get(), **altro)


def vettori_piccoli(testi: list[str]) -> list[list[float]]:
    """Vettori normalizzati (norma 1) con text-embedding-3-small: il coseno è il prodotto scalare."""
    r = modello._post(modello.VETTORI, {"model": MODELLO_VETTORI_PICCOLI, "input": [t[:8000] for t in testi]}, 60)
    modello._somma((r.get("usage") or {}).get("total_tokens", 0) * 0.02 / 1e6, IP.get())
    out = []
    for d in sorted(r["data"], key=lambda d: d["index"]):
        v = d["embedding"]
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


def scalare(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
