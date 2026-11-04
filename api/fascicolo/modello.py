"""Chiamate a OpenAI con la libreria standard, per il fascicolo: chat (Chat Completions), testo strutturato e vettori
delle domande. Le domande vanno nello stesso spazio dei brani (pipeline/vettori.py: text-embedding-3-large a 1.024
dimensioni). La spesa si somma a quella della chat (agente._conta), così vale lo stesso tetto giornaliero."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from contextvars import ContextVar

from pipeline.ambiente import env

from .. import agente

CHAT = "https://api.openai.com/v1/chat/completions"
VETTORI = "https://api.openai.com/v1/embeddings"
MODELLO_VETTORI, DIMENSIONI = "text-embedding-3-large", 1024
PREZZO_VETTORI = 0.13                      # dollari per milione di token, senza Batch API
# prezzi per milione di token (input, input in cache, output), da tenere allineati al listino OpenAI; un modello che
# non c'è si conta per eccesso.
PREZZI = dict(agente.PREZZI)
PREZZI.update({"gpt-4.1": (2.0, 0.5, 8.0), "gpt-4.1-mini": (0.4, 0.1, 1.6)})
# la spesa di un fascicolo, per il registro: chi la vuole contare mette qui una lista [0.0] (i thread la ereditano
# con contextvars.copy_context)
SPESA: ContextVar[list | None] = ContextVar("fascicolo_spesa", default=None)


def _somma(dollari: float, ip: str | None) -> None:
    agente._conta(ip or "fascicolo", 0, dollari)
    s = SPESA.get()
    if s is not None:
        s[0] += dollari


class ModelloNonDisponibile(RuntimeError):
    """OpenAI non risponde, manca la chiave o è finito il tetto di spesa."""


def _post(url: str, corpo: dict, timeout: float = 120) -> dict:
    try:
        chiave = env("OPENAI_API_KEY")
    except KeyError as e:
        raise ModelloNonDisponibile("manca la chiave del modello") from e
    if not agente.controlla_spesa():
        raise ModelloNonDisponibile("tetto di spesa di oggi raggiunto")
    req = urllib.request.Request(url, json.dumps(corpo).encode(), {"Content-Type": "application/json",
                                                                   "Authorization": f"Bearer {chiave}"})
    for tentativo in (1, 2, 3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429 or tentativo == 3:
                raise ModelloNonDisponibile(f"il modello non risponde ({e.code})") from e
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as e:
            if tentativo == 3:
                raise ModelloNonDisponibile("il modello non risponde") from e
        time.sleep(2 * tentativo)
    raise ModelloNonDisponibile("il modello non risponde")


def _spesa(modello: str, uso: dict, ip: str | None) -> None:
    pin, pcache, pout = PREZZI.get(modello, (2.0, 0.2, 15.0))     # modello senza prezzo: stima per eccesso
    cache = (uso.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    dollari = ((uso.get("prompt_tokens", 0) - cache) * pin + cache * pcache + uso.get("completion_tokens", 0) * pout) / 1e6
    _somma(dollari, ip)


def chat(modello: str, messaggi: list[dict], ip: str | None = None, json_schema: dict | None = None,
         massimo: int | None = None, timeout: float = 180, **altro) -> str:
    """Il testo della risposta. Con `json_schema` (uno schema JSON) la risposta è un JSON valido per quello schema."""
    corpo = {"model": modello, "messages": messaggi, "store": False, **altro}
    if massimo:
        corpo["max_completion_tokens"] = massimo
    if json_schema:
        corpo["response_format"] = {"type": "json_schema", "json_schema": {"name": "risposta", "schema": json_schema, "strict": True}}
    r = _post(CHAT, corpo, timeout)
    _spesa(modello, r.get("usage") or {}, ip)
    return (r["choices"][0]["message"].get("content") or "").strip()


def vettori(testi: list[str], ip: str | None = None) -> list[list[float]]:
    """I vettori di alcuni testi brevi (domande, temi), nello spazio dei brani."""
    r = _post(VETTORI, {"model": MODELLO_VETTORI, "dimensions": DIMENSIONI, "input": [t[:8000] for t in testi]}, 60)
    _somma((r.get("usage") or {}).get("total_tokens", 0) * PREZZO_VETTORI / 1e6, ip)
    return [d["embedding"] for d in sorted(r["data"], key=lambda d: d["index"])]


def letterale(v: list[float]) -> str:
    """Un vettore come letterale halfvec di Postgres: «'[0.1,…]'::halfvec(1024)» si scrive con questo testo."""
    return "[" + ",".join(f"{x:.6g}" for x in v) + "]"
