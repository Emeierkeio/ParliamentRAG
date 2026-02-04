"""
Stage 2: Sectional Writer

Writes one section per party + government, using ONLY retrieved evidence.
All 10 parties must have sections.
"""
import json
import logging
from typing import List, Dict, Any, Optional, AsyncIterator

import openai

from ...config import get_config, get_settings

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

REGOLE FONDAMENTALI:
1. Usa SOLO le evidenze fornite - NON inventare
2. I nomi degli oratori in GRASSETTO: **Nome Cognome**
3. MASSIMO 1-2 citazioni per sezione
4. Ogni frase deve aggiungere valore - NO ripetizioni
5. Tono neutro e professionale

COERENZA SEMANTICA (CRITICO):
Il testo che introduce la citazione DEVE riassumere/anticipare il contenuto della citazione stessa.
LEGGI ATTENTAMENTE l'evidenza e scrivi un'introduzione che ne rifletta il significato.

ESEMPIO COERENTE ✓:
Evidenza: "Il sistema sanitario è in crisi per mancanza di fondi"
Testo: **Mario Rossi** denuncia la crisi del sistema, affermando che la sanità [CIT:id].

ESEMPIO INCOERENTE ✗:
Evidenza: "Il sistema sanitario è in crisi per mancanza di fondi"
Testo: **Mario Rossi** elogia la riforma, sottolineando come il decreto [CIT:id].
← Il testo parla di "elogio" ma la citazione è una "denuncia" - INCOERENTE!

INTEGRAZIONE CITAZIONI:
Le citazioni devono essere INTEGRATE naturalmente nel flusso del testo.
Il sistema sostituirà [CIT:ID] con la citazione completa tra virgolette.

REGOLA GRAMMATICALE:
La frase deve essere sempre completa (soggetto-predicato-oggetto).
INSERISCI SEMPRE UN SOGGETTO prima della citazione.

COSTRUZIONI CORRETTE:
- "...sottolineando come il decreto [CIT:id]"
- "...affermando che la riforma [CIT:id]"
- "...evidenziando come il sistema [CIT:id]"
- "...dichiarando che il governo [CIT:id]"

ESEMPI CORRETTI ✓:
**Marco Rossi** critica la gestione, affermando che il sistema [CIT:id].
**Laura Bianchi** difende il provvedimento, sottolineando come la misura [CIT:id].

ESEMPI ERRATI ✗:
**Marco Rossi** critica la riforma [CIT:id]. ← manca costruzione introduttiva
**Marco Rossi** sottolinea come [CIT:id]. ← MANCA IL SOGGETTO
**Marco Rossi** parla del CUP unico [CIT:id]. ← ma la citazione parla di altro tema

ERRORI DA EVITARE:
✗ Testo introduttivo INCOERENTE con il contenuto della citazione
✗ Citazioni "appese" senza costruzione introduttiva
✗ Mancanza del soggetto prima della citazione

STRUTTURA:
### [NOME PARTITO]
[2-4 frasi con citazioni BEN INTEGRATE e COERENTI con il testo]"""

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

    async def write_sections(
        self,
        query: str,
        claims: List[Dict[str, Any]],
        evidence_by_party: Dict[str, List[Dict[str, Any]]],
        government_evidence: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Write sections for all parties.

        Yields section data as they are generated (for streaming).

        Args:
            query: Original user query
            claims: Claims from analyst stage
            evidence_by_party: Evidence grouped by party
            government_evidence: Evidence from government members

        Yields:
            Section dictionaries with party, content, citations
        """
        # Write government section first if there's evidence
        if government_evidence:
            section = await self._write_section(
                query=query,
                party="GOVERNO",
                evidence=government_evidence,
                claims=claims,
                is_government=True
            )
            yield section

        # Write section for each party
        for party in ALL_PARTIES:
            evidence = evidence_by_party.get(party, [])
            section = await self._write_section(
                query=query,
                party=party,
                evidence=evidence,
                claims=claims,
                is_government=False
            )
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

        # Build evidence context
        evidence_context = self._build_evidence_context(evidence)

        # Build claims relevant to this party
        party_claims = [c for c in claims if c.get("party") == party or c.get("party") is None]

        user_prompt = f"""Domanda: {query}

Partito: {party}
{"(Sezione Governo)" if is_government else ""}

Evidenze disponibili (usa max 1-2):
{evidence_context}

SCRIVI UNA SEZIONE BREVE (max 3-4 frasi):
- Usa **grassetto** per i nomi
- Max 1-2 citazioni con formato [CIT:ID_COMPLETO]
- LEGGI l'evidenza e scrivi un testo introduttivo COERENTE con il suo contenuto
- INTEGRA le citazioni con un SOGGETTO: es. "sottolineando come il decreto [CIT:id]"
- NON scrivere di un tema se la citazione parla di altro
"""

        try:
            response = self.client.chat.completions.create(
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
        max_evidence: int = 10
    ) -> str:
        """Build evidence context string for the prompt."""
        lines = []

        for e in evidence[:max_evidence]:
            eid = e.get("evidence_id", "unknown")
            speaker = e.get("speaker_name", "")
            date = e.get("date", "")
            text = e.get("chunk_text", "")[:500]  # Truncate for context

            lines.append(f"""
[ID: {eid}]
Speaker: {speaker}
Date: {date}
Text: {text}
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
