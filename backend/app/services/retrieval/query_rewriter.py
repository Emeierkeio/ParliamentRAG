"""
Minimal query rewriter for parliamentary retrieval.

Expands short or ambiguous queries (acronyms, proper names of directives/laws)
with related Italian parliamentary terms so that:
  - The query embedding is more semantically specific
  - The graph channel keyword search finds fewer unrelated omnibus acts

Only rewrites queries up to `max_query_words` words; longer queries are
considered already descriptive enough.
"""
import logging
from typing import Optional

from ...key_pool import make_client
from ...config import get_config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Sei un esperto del parlamento italiano.
Data una query di ricerca parlamentare, restituisci una versione espansa \
con termini correlati in italiano che migliorino la precisione della ricerca.

Regole:
- OGNI termine va interpretato nella sua accezione POLITICO-PARLAMENTARE \
corrente, mai in accezioni scientifiche/naturalistiche/tecniche di altri \
domini. Es. "remigrazione" è il concetto politico di rimpatrio degli \
immigrati ("remigrazione rimpatri espulsioni immigrazione irregolare") — \
NON la migrazione degli uccelli.
- Espandi acronimi (es. "SSN" → "Servizio Sanitario Nazionale sanità \
sistema sanitario riforma sanitaria LEA")
- Espandi nomi propri di direttive o leggi (es. "Bolkestein" → \
"direttiva Bolkestein concessioni balneari stabilimenti balneari \
liberalizzazione servizi")
- Se non conosci CON CERTEZZA il significato politico del termine, \
restituisci la query INVARIATA: un'espansione sbagliata avvelena la \
ricerca, una mancata espansione no.
- Massimo 15 parole totali
- Solo italiano, nessuna spiegazione, solo la query espansa\
"""


class QueryRewriter:
    """
    Expands short/ambiguous queries with related parliamentary terms.

    Uses a cheap, fast model (gpt-4.1-nano) and always falls back to the
    original query on any error so retrieval is never blocked.
    """

    def __init__(self) -> None:
        self._client = make_client()
        self._config = get_config()

    def rewrite(self, query: str) -> str:
        """
        Return an expanded version of `query`, or the original if rewriting
        is disabled, the query is already long, or the LLM call fails.
        """
        cfg = self._config.load_config().get("query_rewriting", {})
        if not cfg.get("enabled", True):
            return query

        max_words = cfg.get("max_query_words", 5)
        if len(query.split()) > max_words:
            return query

        model = cfg.get("model", "gpt-4.1-nano")

        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                max_tokens=60,
                temperature=0,
            )
            rewritten = response.choices[0].message.content.strip()
            if rewritten:
                logger.info(f"[QUERY_REWRITE] '{query}' → '{rewritten}'")
                return rewritten
        except Exception as exc:
            logger.warning(f"[QUERY_REWRITE] failed, using original: {exc}")

        return query
