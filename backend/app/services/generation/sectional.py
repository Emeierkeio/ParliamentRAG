"""
Stage 2: Sectional Writer

Writes one section per party + government, using ONLY retrieved evidence.
All 10 parties must have sections.

CITATION-FIRST APPROACH:
Citations are pre-extracted BEFORE the LLM writes the text.
This ensures the introductory text matches the actual citation content.
"""
import json
import logging
from typing import List, Dict, Any, Optional, AsyncIterator

import openai

from ...config import get_config, get_settings
from ..citation import extract_best_sentences

logger = logging.getLogger(__name__)


# All 10 parliamentary groups (must all appear in output)
ALL_PARTIES = [
    "FRATELLI D'ITALIA",
    "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA",
    "LEGA - SALVINI PREMIER",
    "MOVIMENTO 5 STELLE",
    "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
    "ALLEANZA VERDI E SINISTRA",
    "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE",
    "ITALIA VIVA-IL CENTRO-RENEW EUROPE",
    "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC E ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE",
    "MISTO",
]


class SectionalWriter:
    """
    Stage 2 of the generation pipeline.

    Writes one section per party using ONLY the retrieved evidence.
    If no evidence exists for a party, writes the configured "no evidence" message.
    """

    SYSTEM_PROMPT = """Sei un redattore parlamentare italiano esperto.
Scrivi sezioni BREVI e INCISIVE (max 3-4 frasi per sezione).

⚠️ APPROCCIO CITATION-FIRST:
Ogni evidenza contiene una ★ CITAZIONE DA USARE già selezionata.
DEVI costruire il testo introduttivo che PREPARI quella citazione.

⚠️⚠️ REGOLA CRITICA - NON COPIARE LA CITAZIONE:
Tu scrivi SOLO il testo introduttivo. Il sistema inserirà automaticamente la citazione.
NON scrivere MAI il contenuto della citazione tra virgolette «».
Scrivi SOLO fino a [CIT:id] e BASTA.

REGOLE FONDAMENTALI:
1. LEGGI la ★ CITAZIONE per capire il TEMA, ma NON copiarla
2. Scrivi un'intro che PREPARI quel contenuto, poi metti [CIT:id]
3. I nomi degli oratori in GRASSETTO: **Nome Cognome**
4. MASSIMO 1-2 citazioni per sezione

PROCESSO DI SCRITTURA:
1. Leggi la ★ CITAZIONE (es: «il conflitto in Ucraina ci riguarda tutti»)
2. Capisci il TEMA: parla di Ucraina e responsabilità collettiva
3. Scrivi intro che prepari quel tema: "ha sottolineato la rilevanza del conflitto per la comunità internazionale, affermando che [CIT:id]."
4. STOP - non aggiungere altro dopo [CIT:id]

ESEMPIO CORRETTO ✓:
★ CITAZIONE: «il sistema sanitario è in crisi per mancanza di fondi»
→ **Mario Rossi** denuncia le difficoltà del sistema sanitario, affermando che [CIT:id].

ESEMPIO SBAGLIATO ✗:
→ **Mario Rossi** denuncia che «il sistema è in crisi» [CIT:id]. ← HAI COPIATO LA CITAZIONE!

COSTRUZIONI CORRETTE (bridge verbale + soggetto):
- "...affermando che il sistema [CIT:id]"
- "...sottolineando come la riforma [CIT:id]"
- "...dichiarando che il governo [CIT:id]"

STRUTTURA OUTPUT:
### [NOME PARTITO]
[2-4 frasi, ogni citazione è SOLO [CIT:id] senza virgolette]"""

    def __init__(self):
        self.config = get_config()
        self.settings = get_settings()
        # Use AsyncOpenAI for true parallel execution with asyncio.gather()
        self.client = openai.AsyncOpenAI(api_key=self.settings.openai_api_key)

        gen_config = self.config.load_config().get("generation", {})
        self.model = gen_config.get("models", {}).get("writer", "gpt-4o")
        self.no_evidence_message = gen_config.get(
            "no_evidence_message",
            "Nel corpus analizzato non risultano interventi rilevanti su questo tema."
        )

    async def write_sections(
        self,
        query: str,
        claims: List[Dict[str, Any]],
        evidence_by_party: Dict[str, List[Dict[str, Any]]],
        government_evidence: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Write sections for all parties IN PARALLEL.

        Yields section data as they are generated (for streaming).

        Args:
            query: Original user query
            claims: Claims from analyst stage
            evidence_by_party: Evidence grouped by party
            government_evidence: Evidence from government members

        Yields:
            Section dictionaries with party, content, citations
        """
        import asyncio

        # Build all tasks for parallel execution
        tasks = []
        task_order = []  # Track order: government first, then parties

        # Government section task (if evidence exists)
        if government_evidence:
            tasks.append(self._write_section(
                query=query,
                party="GOVERNO",
                evidence=government_evidence,
                claims=claims,
                is_government=True
            ))
            task_order.append("GOVERNO")

        # Party section tasks
        for party in ALL_PARTIES:
            evidence = evidence_by_party.get(party, [])
            tasks.append(self._write_section(
                query=query,
                party=party,
                evidence=evidence,
                claims=claims,
                is_government=False
            ))
            task_order.append(party)

        # Execute ALL sections in parallel
        logger.info(f"Writing {len(tasks)} sections in parallel...")
        sections = await asyncio.gather(*tasks)

        # Yield results in order
        for section in sections:
            yield section

    async def _write_section(
        self,
        query: str,
        party: str,
        evidence: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
        is_government: bool = False
    ) -> Dict[str, Any]:
        """Write a single section for a party or government."""

        if not evidence:
            # No evidence - return standard message
            return {
                "party": party,
                "content": f"## {party}\n\n{self.no_evidence_message}",
                "citations": [],
                "has_evidence": False,
            }

        # Build evidence context with pre-extracted citations
        evidence_context = self._build_evidence_context(evidence, query)

        # Build claims relevant to this party
        party_claims = [c for c in claims if c.get("party") == party or c.get("party") is None]

        user_prompt = f"""Domanda: {query}

Partito: {party}
{"(Sezione Governo/Esecutivo)" if is_government else ""}

Evidenze disponibili (usa max 1-2):
{evidence_context}

⚠️ ISTRUZIONI CITATION-FIRST:
1. LEGGI la ★ CITAZIONE per capire il TEMA
2. Scrivi SOLO l'introduzione che prepara quel tema
3. Metti [CIT:ID_COMPLETO] dove andrà la citazione
4. ⚠️ NON COPIARE MAI il testo della citazione tra «» - il sistema lo inserirà!

FORMATO OUTPUT:
**Nome Cognome** [contesto], affermando che [CIT:id].

⚠️ SBAGLIATO: **Rossi** dice che «testo citazione» [CIT:id]. ← NON FARE QUESTO!
✓ GIUSTO: **Rossi** interviene sul tema, affermando che [CIT:id].
"""

        try:
            # Async call for true parallel execution
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500  # Reduced for concise output
            )

            content = response.choices[0].message.content

            # Extract citation IDs - primarily [CIT:id] format
            import re
            citation_ids = re.findall(r'\[CIT:([^\]]+)\]', content)

            # Also catch any legacy ["text"](id) format and extract just the ID
            legacy_ids = re.findall(r'\]\(([^)]+)\)', content)
            citation_ids.extend(legacy_ids)

            # Build valid evidence IDs set for validation
            valid_evidence_ids = {e.get("evidence_id") for e in evidence}

            # Validate and filter citation IDs
            validated_ids = []
            invalid_ids = []
            for cit_id in citation_ids:
                if cit_id in valid_evidence_ids:
                    validated_ids.append(cit_id)
                else:
                    invalid_ids.append(cit_id)
                    logger.warning(f"Invalid citation ID '{cit_id}' not in evidence list for {party}")

            # Log if we found invalid citations (possible truncation)
            if invalid_ids:
                logger.warning(f"Section {party}: {len(invalid_ids)} invalid citation IDs found: {invalid_ids[:5]}")

            # Map validated IDs to actual evidence
            citations = []
            seen_ids = set()
            for cit_id in validated_ids:
                if cit_id in seen_ids:
                    continue
                seen_ids.add(cit_id)
                for e in evidence:
                    if e.get("evidence_id") == cit_id:
                        citations.append({
                            "citation_id": cit_id,
                            "evidence_id": e.get("evidence_id"),
                            "speaker_name": e.get("speaker_name"),
                            "party": e.get("party"),
                            "date": str(e.get("date", "")),
                        })
                        break

            return {
                "party": party,
                "content": content,
                "citations": citations,
                "has_evidence": True,
            }

        except Exception as e:
            logger.error(f"Section writing failed for {party}: {e}")
            return {
                "party": party,
                "content": f"## {party}\n\n[Errore nella generazione della sezione]",
                "citations": [],
                "has_evidence": False,
                "error": str(e),
            }

    def _build_evidence_context(
        self,
        evidence: List[Dict[str, Any]],
        query: str,
        max_evidence: int = 10
    ) -> str:
        """
        Build evidence context with PRE-EXTRACTED citations.

        CITATION-FIRST: Extract the exact citation BEFORE the LLM writes,
        so the LLM can construct text that matches the citation content.
        """
        lines = []

        for e in evidence[:max_evidence]:
            eid = e.get("evidence_id", "unknown")
            speaker = e.get("speaker_name", "")
            date = e.get("date", "")

            # Get the full quote text for extraction
            quote_text = e.get("quote_text", "") or e.get("chunk_text", "")

            # PRE-EXTRACT the citation that will actually be used
            # This is the KEY change: LLM sees the EXACT citation
            if quote_text and query:
                extracted_citation = extract_best_sentences(
                    text=quote_text,
                    query=query,
                    max_sentences=1,
                    max_chars=150
                )
                # Store pre-extracted citation in evidence for later use by Surgeon
                e["pre_extracted_citation"] = extracted_citation
            else:
                extracted_citation = quote_text[:150] if quote_text else ""
                e["pre_extracted_citation"] = extracted_citation

            # Also provide context (truncated) for understanding
            context = e.get("chunk_text", "")[:300]

            lines.append(f"""
[ID: {eid}]
Speaker: {speaker}
Date: {date}
★ CITAZIONE DA USARE: «{extracted_citation}»
Contesto: {context}
---""")

        return "\n".join(lines)

    def write_sections_sync(
        self,
        query: str,
        claims: List[Dict[str, Any]],
        evidence_by_party: Dict[str, List[Dict[str, Any]]],
        government_evidence: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Synchronous version of write_sections.

        Returns all sections as a list.
        """
        import asyncio

        async def collect():
            sections = []
            async for section in self.write_sections(
                query, claims, evidence_by_party, government_evidence
            ):
                sections.append(section)
            return sections

        return asyncio.run(collect())
