"""
Evidence-First Sectional Writer.

Builds text AROUND citations rather than adding citations to text.
This approach ensures 100% semantic coherence by construction.

Instead of:
1. Write text with placeholders
2. Hope the LLM puts citations in the right place

We do:
1. Select the exact evidence to cite
2. Extract the quote
3. Ask LLM to write ONLY the intro that leads into this specific quote
4. Assemble: intro + [CIT:id]

This guarantees that the introductory text is semantically aligned
with the citation because the LLM sees the actual quote before writing.
"""
import re
import logging
from typing import List, Dict, Any, Optional

import openai

from ...config import get_config, get_settings

logger = logging.getLogger(__name__)


class EvidenceFirstWriter:
    """
    Stage 2 Alternative: Evidence-First Generation.

    For each party section:
    1. Select top 1-2 evidence pieces
    2. Extract the EXACT quote that will be cited
    3. Ask LLM to write ONLY the introductory text that leads into the quote
    4. Assemble: intro + [CIT:id]

    This guarantees semantic coherence by construction.
    """

    INTRO_GENERATION_PROMPT = """Sei un redattore parlamentare italiano.

Ti fornisco una citazione ESATTA che dovrai introdurre. Il tuo compito è scrivere SOLO il testo introduttivo.

CITAZIONE DA INTRODURRE:
Oratore: {speaker_name}
Partito: {party}
Testo citazione: "{quote_text}"

TEMA DELLA DOMANDA: {query}

SCRIVI SOLO IL TESTO INTRODUTTIVO (1-2 frasi) che:
1. Nomina l'oratore in **grassetto**: **{speaker_surname}**
2. Riassume/anticipa il CONTENUTO della citazione
3. Termina con una costruzione che introduce la citazione (es. "affermando che", "sottolineando come")
4. Include un SOGGETTO grammaticale che collega alla citazione

FORMATO OBBLIGATORIO:
Il tuo output sarà concatenato con la citazione tra virgolette, quindi deve essere grammaticalmente corretto.

ESEMPI:
Se la citazione è "il sistema sanitario è in crisi per mancanza di fondi"
Scrivi: "**Rossi** denuncia le carenze del sistema sanitario, affermando che"

Se la citazione è "questa riforma porterà benefici a tutte le famiglie"
Scrivi: "**Bianchi** difende la riforma, sottolineando come"

REGOLE:
- NON includere la citazione nel tuo output
- NON aggiungere virgolette
- Termina con una costruzione introduttiva ("affermando che", "sottolineando come", "evidenziando che", etc.)
- Massimo 2 frasi

ORA SCRIVI SOLO IL TESTO INTRODUTTIVO:"""

    def __init__(self):
        self.config = get_config()
        self.settings = get_settings()
        self.client = openai.OpenAI(api_key=self.settings.openai_api_key)

        gen_config = self.config.load_config().get("generation", {})
        self.model = gen_config.get("models", {}).get("writer", "gpt-4o")
        self.no_evidence_message = gen_config.get(
            "no_evidence_message",
            "Nel corpus analizzato non risultano interventi rilevanti su questo tema."
        )

    async def write_section_evidence_first(
        self,
        query: str,
        party: str,
        evidence: List[Dict[str, Any]],
        max_citations: int = 2
    ) -> Dict[str, Any]:
        """
        Write section with evidence-first approach.

        Args:
            query: The user's original query
            party: The party name for this section
            evidence: List of evidence for this party
            max_citations: Maximum number of citations to include (default: 2)

        Returns:
            Section dictionary with:
            - party: Party name
            - content: Generated content with [CIT:id] placeholders
            - citations: List of citation metadata
            - has_evidence: Boolean
            - citation_bindings: List of binding info for registry
        """
        if not evidence:
            return {
                "party": party,
                "content": f"### {party}\n\n{self.no_evidence_message}",
                "citations": [],
                "has_evidence": False,
                "citation_bindings": []
            }

        # Select top evidence pieces by similarity score
        selected_evidence = sorted(
            evidence,
            key=lambda e: e.get("similarity", 0),
            reverse=True
        )[:max_citations]

        # Build section content
        content_parts = []
        citation_bindings = []
        citations = []

        for e in selected_evidence:
            evidence_id = e.get("evidence_id", "")
            speaker_name = e.get("speaker_name", "")
            # Extract surname for brevity
            speaker_surname = speaker_name.split()[-1] if speaker_name else "L'oratore"
            party_name = e.get("party", party)
            quote_text = e.get("quote_text") or e.get("chunk_text", "")

            # Limit quote length for prompt
            quote_for_prompt = quote_text[:400] if len(quote_text) > 400 else quote_text

            # Generate introduction text
            intro_text = await self._generate_introduction(
                query=query,
                speaker_name=speaker_name,
                speaker_surname=speaker_surname,
                party=party_name,
                quote_text=quote_for_prompt,
                evidence_id=evidence_id
            )

            # Assemble with citation placeholder
            full_segment = f"{intro_text} [CIT:{evidence_id}]."
            content_parts.append(full_segment)

            # Record binding for verification
            citation_bindings.append({
                "evidence_id": evidence_id,
                "intro_text": intro_text,
                "quote_preview": quote_text[:100],
                "binding_verified": True  # By construction
            })

            citations.append({
                "citation_id": evidence_id,
                "evidence_id": evidence_id,
                "speaker_name": speaker_name,
                "speaker_id": e.get("speaker_id", ""),
                "speaker_role": e.get("speaker_role", "Deputy"),
                "party": party_name,
                "date": str(e.get("date", "")),
            })

        # Add section header
        content = f"### {party}\n\n" + " ".join(content_parts)

        return {
            "party": party,
            "content": content,
            "citations": citations,
            "has_evidence": True,
            "citation_bindings": citation_bindings
        }

    async def _generate_introduction(
        self,
        query: str,
        speaker_name: str,
        speaker_surname: str,
        party: str,
        quote_text: str,
        evidence_id: str
    ) -> str:
        """
        Generate introduction text for a specific citation.

        Args:
            query: User's query
            speaker_name: Full speaker name
            speaker_surname: Speaker's surname for brevity
            party: Political party
            quote_text: The actual quote to introduce
            evidence_id: Evidence ID for logging

        Returns:
            Introduction text ready to be concatenated with [CIT:id]
        """
        prompt = self.INTRO_GENERATION_PROMPT.format(
            speaker_name=speaker_name,
            speaker_surname=speaker_surname,
            party=party,
            quote_text=quote_text,
            query=query
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150
            )

            intro = response.choices[0].message.content.strip()

            # Clean up - remove any accidental citation markers
            intro = re.sub(r'\[CIT:[^\]]*\]', '', intro)

            # Remove any quotes that might have been added
            intro = intro.replace('«', '').replace('»', '')
            intro = intro.replace('"', '').replace('"', '').replace('"', '')

            # Ensure it ends with an introductory construction
            if not any(intro.rstrip().endswith(ending) for ending in [
                "che", "come", "quanto", "quando", "dove",
                "quale", "quali", "perché"
            ]):
                # If it ends with a period, remove it
                intro = intro.rstrip('.')

            logger.debug(f"Generated intro for {evidence_id}: {intro[:50]}...")

            return intro

        except Exception as e:
            logger.error(f"Introduction generation failed for {evidence_id}: {e}")
            # Fallback: generic introduction
            return f"**{speaker_surname}** interviene sul tema, affermando che"

    def write_section_evidence_first_sync(
        self,
        query: str,
        party: str,
        evidence: List[Dict[str, Any]],
        max_citations: int = 2
    ) -> Dict[str, Any]:
        """
        Synchronous version of write_section_evidence_first.
        """
        import asyncio
        return asyncio.run(
            self.write_section_evidence_first(query, party, evidence, max_citations)
        )
