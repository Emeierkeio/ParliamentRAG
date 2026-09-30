"""Opt-in mailing list for project news and evaluation surveys, held by Brevo.

The address goes straight to Brevo's double opt-in flow and is never written
to our database or logs. The request carries no chat id, query or feedback
id: linking an address to parliamentary questions would reveal political
interests (GDPR art. 9). Brevo stores the confirmation date and IP as proof
of consent and adds the unsubscribe link to every campaign.
"""
import logging
import re
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/newsletter", tags=["Newsletter"])

BREVO_DOI_URL = "https://api.brevo.com/v3/contacts/doubleOptinConfirmation"

# Deliberately loose: valid addresses defeat strict regexes, and the
# confirmation email is the real check.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _configured() -> bool:
    s = get_settings()
    return bool(s.brevo_api_key and s.brevo_list_id and s.brevo_doi_template_id)


class SubscribeRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    consent: Literal[True]


@router.get("")
async def newsletter_status():
    return {"enabled": _configured()}


@router.post("/subscribe")
async def subscribe(payload: SubscribeRequest):
    if not _configured():
        raise HTTPException(status_code=503, detail="newsletter disabled")
    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="invalid email")

    s = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.post(
            BREVO_DOI_URL,
            headers={"api-key": s.brevo_api_key, "accept": "application/json"},
            json={
                "email": email,
                "includeListIds": [int(s.brevo_list_id)],
                "templateId": int(s.brevo_doi_template_id),
                "redirectionUrl": f"{s.public_site_url}/newsletter/confirmed",
            },
        )
    # An address already on the list gets the same answer as a new one: the
    # endpoint must not reveal who is subscribed.
    if res.status_code >= 400 and "duplicate" not in res.text.lower():
        logger.warning(f"[NEWSLETTER] brevo {res.status_code}: {res.text[:200]}")
        raise HTTPException(status_code=502, detail="subscription failed")
    logger.info("[NEWSLETTER] confirmation requested")
    return {"ok": True}
