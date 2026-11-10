"""L'indirizzo IP di chi chiama, per i limiti. Dietro un proxy l'IP vero arriva in X-Forwarded-For, che si legge solo se
l'ambiente lo dice (API_PROXY=1): altrimenti chiunque potrebbe scriverlo."""

from __future__ import annotations

from fastapi import Request

from pipeline.ambiente import env


def ip(req: Request) -> str:
    if env("API_PROXY", "0") == "1" and req.headers.get("x-forwarded-for"):
        return req.headers["x-forwarded-for"].split(",")[-1].strip()
    return req.client.host if req.client else "?"


ESENTE = "esente:"


def chi(req: Request) -> str:
    """L'IP per i limiti della chat; chi ha fatto l'accesso ai pannelli (/accedi) è segnato come esente dal limite orario
    (il tetto di spesa giornaliero vale per tutti)."""
    from .accesso import dentro
    try:
        return ESENTE + ip(req) if dentro(req) else ip(req)
    except Exception:                                  # noqa: BLE001 — senza credenziali configurate nessuno è esente
        return ip(req)
