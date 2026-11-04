"""L'indirizzo IP di chi chiama, per i limiti. Dietro un proxy l'IP vero arriva in X-Forwarded-For, che si legge solo se
l'ambiente lo dice (API_PROXY=1): altrimenti chiunque potrebbe scriverlo."""

from __future__ import annotations

from fastapi import Request

from pipeline.ambiente import env


def ip(req: Request) -> str:
    if env("API_PROXY", "0") == "1" and req.headers.get("x-forwarded-for"):
        return req.headers["x-forwarded-for"].split(",")[-1].strip()
    return req.client.host if req.client else "?"
