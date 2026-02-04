"""
Stage 3: Narrative Integrator

Ensures coherence across sections WITHOUT merging party positions.
Each party's view must remain distinct and attributable.

Includes citation guard functionality to verify citations
are preserved during integration.
"""
import re
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

import openai

from ...config import get_config, get_settings

if TYPE_CHECKING:
    from .citation_registry import CitationRegistry

logger = logging.getLogger(__name__)


class NarrativeIntegrator:
    """
    Stage 3 of the generation pipeline.

    Ensures narrative coherence while maintaining:
    - Clear separation between party positions
    - No synthesis that merges or confuses views
    - Logical flow from government to opposition
    """

    SYSTEM_PROMPT = """Sei un editor parlamentare. Crea un documento CONCISO e ben formattato.

STRUTTURA:

## Introduzione
2-3 frasi sul tema (NO posizioni anticipate)

## Posizioni della Maggioranza

Per Fratelli d'Italia, **Cognome** afferma che «citazione diretta» [CIT:xxx_chunk_1].

Per la Lega, **Cognome** critica la riforma: «citazione diretta» [CIT:xxx_chunk_2].

## Posizioni dell'Opposizione

Per il PD, **Cognome** sostiene che «citazione diretta» [CIT:xxx_chunk_3].

Per il M5S, **Cognome** propone: «citazione diretta» [CIT:xxx_chunk_4].

FORMATO:
- NON usare titoli/header per i partiti (NO ###, NO MAIUSCOLE)
- Integra il nome del partito nel testo: "Per [Partito], **Cognome** sostiene..."
- Cognomi dei deputati SEMPRE in **grassetto**
- Ogni partito è un paragrafo separato (riga vuota tra uno e l'altro)
- Abbrevia i nomi: "Lega", "Forza Italia", "PD", "M5S", "FdI"

COLLEGAMENTO TESTO-CITAZIONE (OBBLIGATORIO):
Ogni citazione DEVE essere introdotta con UN bridge o due punti:

✅ CORRETTO (bridge verbale):
- **Rossi** afferma che «testo citazione» [CIT:...]
- **Rossi** sostiene che «testo citazione» [CIT:...]
- **Rossi** critica la riforma, affermando che «testo citazione» [CIT:...]
- **Rossi** evidenzia come «testo citazione» [CIT:...]

✅ CORRETTO (due punti):
- **Rossi** critica la riforma: «testo citazione» [CIT:...]
- La posizione di **Rossi** è chiara: «testo citazione» [CIT:...]

❌ SBAGLIATO (citazione scollegata):
- **Rossi** critica la riforma. «testo citazione» [CIT:...]
- **Rossi** è contrario «testo citazione» [CIT:...]

REGOLE CITAZIONI (CRITICHE):
⚠️ I marcatori [CIT:...] sono ID tecnici. Devono essere copiati ESATTAMENTE carattere per carattere.
⚠️ NON modificare, abbreviare, o riformulare MAI il contenuto tra [CIT: e ]
⚠️ Esempio corretto: [CIT:leg19_sed531_tit00120.sub00010.int00190_chunk_4]
⚠️ Se una frase contiene [CIT:...], DEVI includerla nel testo finale con il marcatore IDENTICO
⚠️ TUTTE le citazioni presenti nell'input DEVONO apparire nell'output

REGOLE GENERALI:
1. Posizioni DISTINTE per partito, un paragrafo ciascuno
2. PRESERVA **grassetto** e «virgolette» nelle citazioni
3. CONCISO - max 2-3 frasi per partito
4. Solo partiti CON contenuto"""

    def __init__(self):
        self.config = get_config()
        self.settings = get_settings()
        self.client = openai.OpenAI(api_key=self.settings.openai_api_key)

        gen_config = self.config.load_config().get("generation", {})
        self.model = gen_config.get("models", {}).get("integrator", "gpt-4o")

    def integrate(
        self,
        query: str,
        sections: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Integrate sections into coherent narrative.

        Args:
            query: Original user query
            sections: List of section dictionaries from Stage 2

        Returns:
            Dictionary with integrated text and metadata
        """
        # Build sections text
        sections_text = self._build_sections_text(sections)

        user_prompt = f"""Domanda: {query}

Sezioni:
{sections_text}

Crea documento CONCISO con Introduzione (2-3 frasi) + sezioni per coalizione.

⚠️ CRITICO:
1. Copia ESATTAMENTE ogni [CIT:...] carattere per carattere - NON modificare gli ID!
2. Ogni citazione DEVE avere un bridge ("afferma che", "sostiene che") O due punti (:) prima della citazione
3. Preserva **grassetto** e «virgolette»
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=2500  # Reduced for concise output
            )

            integrated_text = response.choices[0].message.content

            # Collect all citations from sections
            all_citations = []
            for section in sections:
                all_citations.extend(section.get("citations", []))

            return {
                "text": integrated_text,
                "citations": all_citations,
                "sections_count": len(sections),
                "parties_with_evidence": sum(
                    1 for s in sections if s.get("has_evidence", False)
                ),
            }

        except Exception as e:
            logger.error(f"Integration failed: {e}")
            # Fallback: concatenate sections without integration
            fallback_text = self._simple_concatenation(sections)
            all_citations = []
            for section in sections:
                all_citations.extend(section.get("citations", []))

            return {
                "text": fallback_text,
                "citations": all_citations,
                "sections_count": len(sections),
                "parties_with_evidence": sum(
                    1 for s in sections if s.get("has_evidence", False)
                ),
                "integration_failed": True,
                "error": str(e),
            }

    # Coalition membership
    MAGGIORANZA = [
        "FRATELLI D'ITALIA",
        "LEGA - SALVINI PREMIER",
        "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE",
        "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC E ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE",
    ]

    OPPOSIZIONE = [
        "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA",
        "MOVIMENTO 5 STELLE",
        "ALLEANZA VERDI E SINISTRA",
        "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE",
        "ITALIA VIVA-IL CENTRO-RENEW EUROPE",
        "MISTO",
    ]

    def _get_section_by_party(self, sections: List[Dict[str, Any]], party: str) -> str:
        """Get content for a specific party from sections."""
        for section in sections:
            if section.get("party") == party:
                return section.get("content", "")
        return ""

    def _build_sections_text(self, sections: List[Dict[str, Any]]) -> str:
        """Build text from all sections, grouped by coalition."""
        parts = []

        # Government first if present
        gov_content = self._get_section_by_party(sections, "GOVERNO")
        if gov_content:
            parts.append("## Posizione del Governo\n\n" + gov_content)

        # Maggioranza sections
        magg_parts = []
        for party in self.MAGGIORANZA:
            content = self._get_section_by_party(sections, party)
            if content:
                magg_parts.append(content)
        if magg_parts:
            parts.append("## Posizioni della Maggioranza\n\n" + "\n\n".join(magg_parts))

        # Opposizione sections
        opp_parts = []
        for party in self.OPPOSIZIONE:
            content = self._get_section_by_party(sections, party)
            if content:
                opp_parts.append(content)
        if opp_parts:
            parts.append("## Posizioni dell'Opposizione\n\n" + "\n\n".join(opp_parts))

        return "\n\n---\n\n".join(parts)

    def _simple_concatenation(self, sections: List[Dict[str, Any]]) -> str:
        """Simple fallback concatenation without LLM integration, grouped by coalition."""
        import re

        def strip_party_header(content: str) -> str:
            """Remove party header lines (## PARTY_NAME)."""
            return re.sub(r'^##\s+[A-Z][^\n]*\n+', '', content, flags=re.MULTILINE)

        parts = []

        # Government first if present
        gov_content = self._get_section_by_party(sections, "GOVERNO")
        if gov_content:
            parts.append("## Posizione del Governo\n\n" + strip_party_header(gov_content))

        # Maggioranza sections
        magg_parts = []
        for party in self.MAGGIORANZA:
            content = self._get_section_by_party(sections, party)
            if content:
                magg_parts.append(strip_party_header(content))
        if magg_parts:
            parts.append("## Posizioni della Maggioranza\n\n" + "\n\n".join(magg_parts))

        # Opposizione sections
        opp_parts = []
        for party in self.OPPOSIZIONE:
            content = self._get_section_by_party(sections, party)
            if content:
                opp_parts.append(strip_party_header(content))
        if opp_parts:
            parts.append("## Posizioni dell'Opposizione\n\n" + "\n\n".join(opp_parts))

        return "\n\n---\n\n".join(parts)

    RETRY_PROMPT = """CORREZIONE RICHIESTA: Alcune citazioni sono state perse o modificate.

DEVI includere TUTTE queste citazioni nel testo, copiando ESATTAMENTE gli ID:
{missing_citations}

REGOLE:
1. Gli ID [CIT:...] devono essere copiati CARATTERE PER CARATTERE, senza modifiche
2. Ogni citazione DEVE essere introdotta con bridge ("afferma che", "sostiene che") O due punti (:)
   ✅ **Rossi** afferma che «testo» [CIT:...]
   ✅ **Rossi** critica: «testo» [CIT:...]
   ❌ **Rossi** critica. «testo» [CIT:...]

Riscrivi il documento includendo TUTTE le citazioni sopra elencate.

Testo da correggere:
{text}

Sezioni originali con citazioni:
{sections}
"""

    def integrate_with_guard(
        self,
        query: str,
        sections: List[Dict[str, Any]],
        registry: Optional['CitationRegistry'] = None
    ) -> Dict[str, Any]:
        """
        Integrate with citation guard.

        Verifies citation preservation pre and post integration.
        Retries with stricter prompt if citations are corrupted.

        Args:
            query: Original user query
            sections: List of section dictionaries from Stage 2
            registry: Optional CitationRegistry for tracking

        Returns:
            Dictionary with integrated text, citations, and verification report
        """
        # Pre-integration: collect expected citations
        expected_citations = set()
        citation_sentences: Dict[str, str] = {}  # Map citation ID to its containing sentence

        for section in sections:
            content = section.get("content", "")
            found = re.findall(r'\[CIT:([^\]]+)\]', content)
            expected_citations.update(found)

            # Store the sentence containing each citation for potential repair
            for cit_id in found:
                # Find the sentence containing this citation
                pattern = rf'[^.!?]*\[CIT:{re.escape(cit_id)}\][^.!?]*[.!?]?'
                matches = re.findall(pattern, content)
                if matches:
                    citation_sentences[cit_id] = matches[0].strip()

        logger.info(f"Integrator guard: {len(expected_citations)} citations expected")

        # Perform standard integration
        result = self.integrate(query, sections)

        # Post-integration: verify citations preserved
        integrated_text = result.get("text", "")
        found_citations = set(re.findall(r'\[CIT:([^\]]+)\]', integrated_text))

        missing = expected_citations - found_citations
        retried = False

        if missing:
            logger.warning(f"Integrator corrupted {len(missing)} citations: {list(missing)}")

            # Retry with stricter prompt
            retried = True
            result = self._retry_integration(
                query, sections, integrated_text, missing, citation_sentences
            )

            # Check again after retry
            integrated_text = result.get("text", "")
            found_citations = set(re.findall(r'\[CIT:([^\]]+)\]', integrated_text))
            still_missing = expected_citations - found_citations

            if still_missing:
                logger.warning(f"Still missing {len(still_missing)} citations after retry")
            else:
                logger.info("All citations recovered after retry")

        # Update registry if provided
        if registry is not None:
            verification = registry.verify_placeholders_in_text(result.get("text", ""))
            result["registry_verification"] = verification

        final_found = set(re.findall(r'\[CIT:([^\]]+)\]', result.get("text", "")))
        result["citation_verification"] = {
            "expected": len(expected_citations),
            "found": len(final_found),
            "missing": list(expected_citations - final_found),
            "retried": retried,
        }
        result["citations_repaired"] = len(final_found) - len(found_citations) if retried else 0

        return result

    def _retry_integration(
        self,
        query: str,
        sections: List[Dict[str, Any]],
        failed_text: str,
        missing_citations: set,
        citation_sentences: Dict[str, str]
    ) -> Dict[str, Any]:
        """Retry integration with explicit citation requirements."""

        # Build list of missing citations with their sentences
        missing_list = []
        for cit_id in missing_citations:
            sentence = citation_sentences.get(cit_id, "")
            missing_list.append(f"- [CIT:{cit_id}] → {sentence}")

        sections_text = self._build_sections_text(sections)

        retry_prompt = self.RETRY_PROMPT.format(
            missing_citations="\n".join(missing_list),
            text=failed_text,
            sections=sections_text
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": retry_prompt}
                ],
                temperature=0.1,  # Even lower for retry
                max_tokens=2500
            )

            integrated_text = response.choices[0].message.content
            logger.info("Retry integration completed")

            # Collect all citations from sections
            all_citations = []
            for section in sections:
                all_citations.extend(section.get("citations", []))

            return {
                "text": integrated_text,
                "citations": all_citations,
                "sections_count": len(sections),
                "parties_with_evidence": sum(
                    1 for s in sections if s.get("has_evidence", False)
                ),
            }

        except Exception as e:
            logger.error(f"Retry integration failed: {e}")
            # Return the original failed text rather than crash
            return {
                "text": failed_text,
                "citations": [],
                "retry_failed": True,
                "error": str(e)
            }
