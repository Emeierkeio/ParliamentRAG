"""Accesso ai pannelli /statistiche e /sistema: una pagina di login (/accedi) che lascia un cookie firmato per 12 ore.

Utente e password stanno in STATISTICHE_UTENTE e STATISTICHE_PASSWORD; senza, i pannelli non esistono (404). Il cookie è
la scadenza più la sua firma HMAC, con una chiave ricavata da utente e password: cambiare la password chiude ogni accesso
aperto. Basic auth resta per gli script (curl -u). Dopo 5 tentativi sbagliati in 15 minuti dallo stesso IP si aspetta.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
import base64
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from pipeline.ambiente import env

from . import agente
from .rete import ip

router = APIRouter()
PAGINA = Path(__file__).parent / "accedi.html"
COOKIE = "pannello"
DURATA = 12 * 3600
TENTATIVI, FINESTRA = 5, 15 * 60
_sbagliati: dict[str, list[float]] = {}
_blocco = threading.Lock()


def _credenziali() -> tuple[str, str]:
    utente, password = env("STATISTICHE_UTENTE", ""), env("STATISTICHE_PASSWORD", "")
    if not utente or not password:
        raise HTTPException(404)
    return utente, password


def _firma(scadenza: int) -> str:
    utente, password = _credenziali()
    chiave = hashlib.sha256(f"pannello|{utente}|{password}".encode()).digest()
    return hmac.new(chiave, str(scadenza).encode(), hashlib.sha256).hexdigest()


def _giusti(u: str, pw: str) -> bool:
    utente, password = _credenziali()
    return secrets.compare_digest(u.encode(), utente.encode()) & secrets.compare_digest(pw.encode(), password.encode())


def dentro(req: Request) -> bool:
    _credenziali()
    scadenza, _, firma = req.cookies.get(COOKIE, "").partition(".")
    if scadenza.isdigit() and int(scadenza) > time.time() and secrets.compare_digest(firma, _firma(int(scadenza))):
        return True
    a = req.headers.get("authorization", "")
    if a.startswith("Basic "):
        try:
            u, _, pw = base64.b64decode(a[6:]).decode().partition(":")
        except ValueError:
            return False
        return _giusti(u, pw)
    return False


def richiedi(req: Request, pagina: bool = False) -> None:
    """Fa passare solo chi ha fatto l'accesso: una pagina rimanda a /accedi, un'API risponde 401 (senza la finestra del browser)."""
    if dentro(req):
        return
    if pagina:
        raise HTTPException(303, headers={"Location": f"/accedi?dopo={quote(req.url.path)}"})
    raise HTTPException(401, "serve l'accesso")


@router.get("/accedi", response_class=HTMLResponse, include_in_schema=False)
def pagina(req: Request) -> Response:
    _credenziali()
    if dentro(req):
        dopo = req.query_params.get("dopo", "")
        return RedirectResponse(dopo if dopo in ("/statistiche", "/sistema") else "/sistema", 303)
    return HTMLResponse(PAGINA.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


class Accesso(BaseModel):
    utente: str = Field(max_length=200)
    password: str = Field(max_length=200)


@router.post("/api/accedi", include_in_schema=False)
def accedi(req: Request, a: Accesso, risposta: Response) -> dict:
    chi, ora = agente._impronta(ip(req)), time.time()
    with _blocco:
        recenti = [t for t in _sbagliati.get(chi, []) if ora - t < FINESTRA]
        _sbagliati[chi] = recenti
        if len(recenti) >= TENTATIVI:
            raise HTTPException(429, f"troppi tentativi: riprova fra {max(1, round((FINESTRA - (ora - recenti[0])) / 60))} minuti")
    if not _giusti(a.utente, a.password):
        with _blocco:
            _sbagliati.setdefault(chi, []).append(ora)
        time.sleep(1)
        raise HTTPException(401, "utente o password sbagliati")
    scadenza = int(ora) + DURATA
    https = req.url.scheme == "https" or req.headers.get("x-forwarded-proto") == "https"
    risposta.set_cookie(COOKIE, f"{scadenza}.{_firma(scadenza)}", max_age=DURATA, httponly=True, secure=https,
                        samesite="strict", path="/")
    return {"ok": True}


@router.get("/esci", include_in_schema=False)
def esci() -> Response:
    r = RedirectResponse("/accedi", 303)
    r.delete_cookie(COOKIE, path="/")
    return r
