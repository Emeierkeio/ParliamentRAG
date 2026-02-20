"""
Stage 1: Claim Analyst

Decomposes the query into atomic claims with evidence requirements.
"""
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional

import openai

from ...config import get_config, get_settings
from ...key_pool import make_client, make_async_client

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds


class ClaimAnalyst:
    """
    Stage 1 of the generation pipeline.

    Analyzes the query and retrieved evidence to produce:
    - List of atomic claims to address
    - Evidence requirements for each claim
    - Party/perspective associations
    """

    SYSTEM_PROMPT = """Sei un analista parlamentare italiano esperto.
Il tuo compito è analizzare una domanda dell'utente e le evidenze parlamentari recuperate
per identificare i claim atomici da affrontare nella risposta.

Per ogni claim devi indicare:
1. Il claim stesso (affermazione specifica)
2. Se richiede evidenza documentale
3. Quale partito/gruppo parlamentare è associato (se applicabile)

OGNI claim DEVE contenere una POSIZIONE CONCRETA (a favore, contro, proposta specifica).
NON produrre claim generici come "Il partito X si è espresso sul tema" o "Il partito X è intervenuto".
Claim valido: "FdI difende il decreto Flussi sostenendo che rafforza i corridoi legali"
Claim NON valido: "FdI ha parlato di immigrazione"

Rispondi SOLO in formato JSON valido con questa struttura:
{
    "claims": [
        {
            "claim_id": "c1",
            "claim": "Affermazione specifica...",
            "evidence_needed": true,
            "party": "NOME_PARTITO o null",
            "priority": "high/medium/low"
        }
    ],
    "query_type": "policy/event/comparison/general",
    "requires_government_view": true/false
}"""

    def __init__(self):
        self.config = get_config()
        self.settings = get_settings()
        self.client = make_client()
        self.async_client = make_async_client()

        gen_config = self.config.load_config().get("generation", {})
        self.model = gen_config.get("models", {}).get("analyst", "gpt-4o")

    def analyze(
        self,
        query: str,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Synchronous analyze (used by main pipeline).
        """
        # Build evidence summary for the prompt
        evidence_summary = self._summarize_evidence(evidence_list)

        # Get all parties represented
        parties_in_evidence = set(e.get("party", "MISTO") for e in evidence_list)

        user_prompt = self._build_prompt(query, parties_in_evidence, evidence_summary)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # Validate structure
            if "claims" not in result:
                result["claims"] = []

            logger.info(f"Analyst identified {len(result.get('claims', []))} claims")

            return result

        except Exception as e:
            logger.error(f"Analyst stage failed: {e}")
            return self._fallback_result(query, e)

    async def analyze_async(
        self,
        query: str,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Async analyze with retry and exponential backoff.
        Used by baseline pipeline to avoid blocking the event loop.
        """
        evidence_summary = self._summarize_evidence(evidence_list)
        parties_in_evidence = set(e.get("party", "MISTO") for e in evidence_list)
        user_prompt = self._build_prompt(query, parties_in_evidence, evidence_summary)

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.async_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)
                if "claims" not in result:
                    result["claims"] = []

                logger.info(f"Analyst (async) identified {len(result.get('claims', []))} claims")
                return result

            except (openai.RateLimitError, openai.APITimeoutError) as e:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"Analyst async attempt {attempt + 1}/{MAX_RETRIES} failed "
                    f"({type(e).__name__}), retrying in {delay:.1f}s..."
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Analyst async failed after {MAX_RETRIES} retries: {e}")
                    return self._fallback_result(query, e)

            except Exception as e:
                logger.error(f"Analyst async stage failed: {e}")
                return self._fallback_result(query, e)

        return self._fallback_result(query, Exception("Max retries exceeded"))

    def _build_prompt(
        self,
        query: str,
        parties_in_evidence: set,
        evidence_summary: str
    ) -> str:
        return f"""Domanda dell'utente: {query}

Partiti presenti nelle evidenze: {', '.join(parties_in_evidence)}

Riepilogo evidenze per partito:
{evidence_summary}

Analizza la domanda e identifica i claim atomici da affrontare.
Assicurati di coprire TUTTI i partiti parlamentari, anche quelli senza evidenza.

I 10 gruppi parlamentari sono:
1. Fratelli d'Italia
2. Partito Democratico - Italia Democratica e Progressista
3. Lega - Salvini Premier
4. Movimento 5 Stelle
5. Forza Italia - Berlusconi Presidente - PPE
6. Alleanza Verdi e Sinistra
7. Azione - Popolari Europeisti Riformatori - Renew Europe
8. Italia Viva - Il Centro - Renew Europe
9. Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro) - MAIE - Centro Popolare
10. Misto

Rispondi in JSON."""

    @staticmethod
    def _fallback_result(query: str, error: Exception) -> Dict[str, Any]:
        return {
            "claims": [
                {
                    "claim_id": "c1",
                    "claim": query,
                    "evidence_needed": True,
                    "party": None,
                    "priority": "high"
                }
            ],
            "query_type": "general",
            "requires_government_view": True,
            "error": str(error)
        }

    def _summarize_evidence(
        self,
        evidence_list: List[Dict[str, Any]],
        max_per_party: int = 3
    ) -> str:
        """Create a summary of evidence grouped by party."""
        by_party: Dict[str, List[str]] = {}

        for evidence in evidence_list:
            party = evidence.get("party", "MISTO")
            if party not in by_party:
                by_party[party] = []

            if len(by_party[party]) < max_per_party:
                # Use chunk_text for summary (not quote_text which is for citation)
                text = evidence.get("chunk_text", "")[:200]
                speaker = evidence.get("speaker_name", "")
                by_party[party].append(f"[{speaker}]: {text}...")

        lines = []
        for party, texts in sorted(by_party.items()):
            lines.append(f"\n{party}:")
            for text in texts:
                lines.append(f"  - {text}")

        return "\n".join(lines) if lines else "Nessuna evidenza disponibile."
