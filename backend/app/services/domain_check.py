"""Out-of-domain query check (issue #22).

Judges whether a query is plausibly a topic of Italian parliamentary debate
and, when it is not, proposes nearby topics the Chamber did discuss. The
check never blocks on its own: any failure returns in_domain=True. The
blocking decision belongs to the evidence gate in the query router, which
uses retrieval similarities.
"""
import json
import logging

from ..key_pool import make_async_client

logger = logging.getLogger(__name__)

# Prompt-friendly language names for the suggestion output
_LANGS = {
    "it": "italiano",
    "en": "English",
    "fr": "français",
    "de": "Deutsch",
    "es": "español",
    "pt": "português",
}

_PROMPT = """Sei il filtro d'ingresso di un sistema di ricerca sui dibattiti \
della Camera dei Deputati italiana (XIX legislatura, dal 2022 a oggi).
Giudica se la query è plausibilmente un tema di dibattito parlamentare italiano.

Fuori dominio: politica interna di altri paesi senza un ruolo dell'Italia, \
sport, cucina, spettacolo, turismo, temi inventati o mai esistiti.
In dominio: qualsiasi tema di politica italiana, e le posizioni italiane su \
questioni internazionali (guerre, trattati, Unione europea).
Nel dubbio: in_domain=true.

Se fuori dominio, proponi SEMPRE 2-3 temi vicini alla query che la Camera ha \
plausibilmente discusso, scritti in {lang}. I temi proposti devono essere \
REALI: correggi la premessa sbagliata della query invece di ripeterla (per \
"conflitto in Belgio", che non esiste, proponi temi su difesa europea o \
missioni internazionali, NON temi che contengono "Belgio").
Rispondi SOLO con JSON: {{"in_domain": true/false, "suggestions": ["..."]}}

Query: {query}"""


async def check_domain(query: str, locale: str = "it") -> dict:
    """Return {"in_domain": bool, "suggestions": [str]}; safe on any error."""
    lang = _LANGS.get(locale, "English")
    try:
        client = make_async_client()
        response = await client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{
                "role": "user",
                "content": _PROMPT.format(lang=lang, query=query),
            }],
            temperature=0,
            max_tokens=150,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        result = {
            "in_domain": bool(data.get("in_domain", True)),
            "suggestions": [str(s) for s in data.get("suggestions", [])][:3],
        }
        if not result["in_domain"]:
            logger.info(
                "[DOMAIN_CHECK] Out of domain: %r, suggestions=%s",
                query, result["suggestions"],
            )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DOMAIN_CHECK] Failed, assuming in-domain: %s", exc)
        return {"in_domain": True, "suggestions": []}
