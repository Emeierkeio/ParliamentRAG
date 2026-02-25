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
from ...key_pool import make_client

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

STRUTTURA (in questo ordine):

## Introduzione
2-3 frasi che inquadrano il tema con DATI CONCRETI forniti nelle statistiche:
- NOMINA specificamente il provvedimento, decreto, DDL o proposta in discussione
- CITA il numero di interventi analizzati e il numero di deputati coinvolti
- INDICA il periodo temporale (data primo e ultimo intervento)
- CITA le sedute specifiche (es. Seduta N. 123) quando disponibili
- NON anticipare le posizioni dei partiti
- NON usare **grassetto** per numeri, statistiche o dati nell'introduzione (il grassetto è riservato SOLO ai cognomi dei deputati)

## Posizione del Governo (se presente)
Ministri e membri dell'esecutivo (es. Meloni, Salvini come ministri, ecc.)

## Posizioni della Maggioranza
Deputati dei partiti di maggioranza (Fratelli d'Italia, Lega, Forza Italia, Noi Moderati)

## Posizioni dell'Opposizione
Deputati dei partiti di opposizione (Partito Democratico, Movimento 5 Stelle, Alleanza Verdi e Sinistra, Azione, Italia Viva, Misto)

⚠️ IMPORTANTE - GOVERNO vs MAGGIORANZA:
- I membri del GOVERNO (ministri, presidente del consiglio) vanno in "Posizione del Governo"
- I DEPUTATI dei partiti di maggioranza vanno in "Posizioni della Maggioranza"
- Esempio: Meloni come Presidente del Consiglio → Governo
- Esempio: Un deputato di Fratelli d'Italia → Maggioranza

⚠️ FILTRO COMPETENZA - POSIZIONE DEL GOVERNO:
In "## Posizione del Governo" includi SOLO:
- Il Presidente del Consiglio (Meloni): sempre ammessa
- Il/i Ministro/i con delega DIRETTAMENTE competente per il tema della query
  (es. Ministro della Salute per sanità, Ministro dell'Economia per fisco/bilancio,
   Ministro della Difesa per questioni militari, Ministro dell'Interno per sicurezza/immigrazione,
   Ministro della Giustizia per riforma giudiziaria, ecc.)
Se nelle sezioni ricevute appare un ministro non competente per il tema trattato
(es. Salvini che commenta la sanità, Nordio che parla di agricoltura), OMETTI quella posizione.
Se dopo questo filtro non rimane nessun membro del governo pertinente, ometti interamente
la sezione "## Posizione del Governo".

FORMATO:
- NON usare titoli/header per i partiti (NO ###, NO MAIUSCOLE)
- Le sezioni di input sono raggruppate in tag [BLOCCO: GOVERNO/MAGGIORANZA/OPPOSIZIONE] e [PARTITO: Nome Partito]
  ⚠️ QUESTI TAG SONO SOLO PER L'INPUT — NON copiarli nell'output. Scrivi tu i tuoi header ## ...
- Ogni sezione di partito inizia con [PARTITO: Nome Partito]: usa quel nome per iniziare il paragrafo nell'output
- Formato OBBLIGATORIO per il primo periodo: "Per [Nome Partito], [testo contestuale]..."
  Esempio: "Per Italia Viva - Il Centro - Renew Europe, il gruppo sostiene con fermezza..."
- Cognomi SEMPRE in **grassetto**
- Ogni partito è un paragrafo separato
- Usa SEMPRE il nome completo del partito (es. "Fratelli d'Italia", "Movimento 5 Stelle", "Partito Democratico"), MAI abbreviazioni

STRUTTURA OBBLIGATORIA PER OGNI PARTITO (3 parti, preserva tutto il contenuto):
1. CONTESTUALIZZAZIONE: 1-2 frasi introduttive che preparano la citazione (usa il testo introduttivo dalla sezione input)
2. CITAZIONE: la frase verbatim con il marcatore {CIT:N} (preserva esattamente dalla sezione input)
3. POSIZIONAMENTO: 1-2 frasi sul posizionamento generale del gruppo (usa il testo di posizionamento dalla sezione input)

⚠️ NON comprimere le sezioni: mantieni il contenuto completo di ciascuna sezione, solo integra il nome del partito all'inizio.

COLLEGAMENTO TESTO-CITAZIONE (OBBLIGATORIO):
Il marcatore {CIT:N} deve essere preceduto da un bridge verbale:
✅ **Rossi** afferma che {CIT:3}
✅ **Rossi** critica la riforma, sottolineando come {CIT:7}
❌ **Rossi** critica la riforma. {CIT:3} ← SBAGLIATO

REGOLE CITAZIONI:
⚠️ {CIT:N} sono marcatori numerici - copiali ESATTAMENTE (es. {CIT:1}, {CIT:12})
⚠️ TUTTI i marcatori {CIT:N} nell'input DEVONO apparire nell'output
⚠️ NON aggiungere testo tra virgolette «» - il sistema inserirà la citazione

VARIAZIONE OBBLIGATORIA DEI BRIDGE VERBALI:
⚠️ OGNI citazione DEVE usare un verbo introduttivo DIVERSO da tutte le altre. ZERO ripetizioni.
Prima di scrivere un bridge, verifica che NON sia già stato usato nel documento.

Repertorio COMPLETO (scegli in base al TONO, ogni verbo usabile UNA SOLA VOLTA):
- Propositivo: propone, invoca, auspica, suggerisce, caldeggia
- Critico: denuncia, contesta, lamenta, critica il fatto che, mette in discussione
- Neutro: rileva, osserva, evidenzia, fa notare, puntualizza, precisa
- Affermativo: afferma, sostiene, dichiara, ribadisce, conferma, assicura
- Interrogativo: solleva interrogativi su, chiede conto di, domanda se

❌ SBAGLIATO (verbo ripetuto):
**Rossi** sottolineando che [CIT:1]... **Bianchi** sottolineando che [CIT:2] ← "sottolineando" usato 2 volte!
✅ CORRETTO (verbi tutti diversi):
**Rossi** sottolineando che [CIT:1]... **Bianchi** contestando che [CIT:2] ← verbi diversi

BILANCIAMENTO (Coverage-based Fairness):
Le sezioni Maggioranza e Opposizione devono avere lunghezza comparabile.
Se una coalizione ha più partiti con evidenze, dai comunque spazio adeguato all'altra.
Non liquidare partiti di opposizione con una sola frase se quelli di maggioranza ne hanno più di due.

REGOLE GENERALI:
1. Posizioni DISTINTE, un paragrafo per partito/ministro
2. PRESERVA **grassetto** e marcatori [CIT:...]
3. Preserva il contenuto completo di ogni sezione (intro + citazione + posizionamento)"""

    def __init__(self):
        self.config = get_config()
        self.settings = get_settings()
        self.client = make_client()

        gen_config = self.config.load_config().get("generation", {})
        self.model = gen_config.get("models", {}).get("integrator", "gpt-4o")

        coalitions = self.config.coalitions
        self.MAGGIORANZA = coalitions.get("maggioranza", [])
        self.OPPOSIZIONE = coalitions.get("opposizione", [])

    def _format_statistics(self, topic_statistics: Optional[Dict[str, Any]]) -> str:
        """Format topic statistics for the integrator prompt."""
        if not topic_statistics:
            return ""

        parts = ["STATISTICHE DEL TEMA (usa questi dati nell'Introduzione):"]

        debate_title = topic_statistics.get("debate_title")
        intervention_count = topic_statistics.get("intervention_count", 0)
        speaker_count = topic_statistics.get("speaker_count", 0)
        first_date = topic_statistics.get("first_date")
        last_date = topic_statistics.get("last_date")

        if debate_title:
            parts.append(f"- Provvedimento/dibattito principale: {debate_title}")
        if intervention_count:
            parts.append(f"- Interventi analizzati: {intervention_count}")
        if speaker_count:
            parts.append(f"- Parlamentari coinvolti: {speaker_count}")
        if last_date:
            date_str = last_date.strftime("%d/%m/%Y") if hasattr(last_date, 'strftime') else str(last_date)
            parts.append(f"- Ultimo intervento: {date_str}")
        if first_date and last_date:
            first_str = first_date.strftime("%d/%m/%Y") if hasattr(first_date, 'strftime') else str(first_date)
            last_str = last_date.strftime("%d/%m/%Y") if hasattr(last_date, 'strftime') else str(last_date)
            parts.append(f"- Periodo: dal {first_str} al {last_str}")

        # Session numbers for academic traceability
        session_numbers = topic_statistics.get("session_numbers", [])
        if session_numbers:
            sorted_sessions = sorted(session_numbers)
            sessions_str = ", ".join(str(s) for s in sorted_sessions[:5])
            if len(sorted_sessions) > 5:
                sessions_str += f" e altre {len(sorted_sessions) - 5}"
            parts.append(f"- Sedute parlamentari: N. {sessions_str}")

        return "\n".join(parts) + "\n"

    def _strip_citations(
        self, sections: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Replace [CIT:long_id] with short numeric {CIT:N} placeholders before LLM call.

        Long IDs like [CIT:leg19_sed569_tit00070.sub00010.int00040_chunk_2] are error-prone
        for the LLM to copy verbatim. Short numeric placeholders drastically reduce corruption.

        Returns:
            (stripped_sections, mapping) where mapping is {"1": "leg19_...", "2": ...}
        """
        counter = 1
        mapping: Dict[str, str] = {}
        stripped = []
        for section in sections:
            content = section.get("content", "")

            def replace_cit(m: re.Match) -> str:
                nonlocal counter
                cit_id = m.group(1)
                key = str(counter)
                mapping[key] = cit_id
                counter += 1
                return f"{{CIT:{key}}}"

            new_content = re.sub(r'\[CIT:([^\]]+)\]', replace_cit, content)
            stripped.append({**section, "content": new_content})
        return stripped, mapping

    def _restore_citations(self, text: str, mapping: Dict[str, str]) -> str:
        """Restore short {CIT:N} placeholders back to original [CIT:long_id] format."""
        def restore(m: re.Match) -> str:
            key = m.group(1)
            original_id = mapping.get(key)
            return f"[CIT:{original_id}]" if original_id else m.group(0)

        return re.sub(r'\{CIT:(\d+)\}', restore, text)

    def integrate(
        self,
        query: str,
        sections: List[Dict[str, Any]],
        topic_statistics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Integrate sections into coherent narrative.

        Args:
            query: Original user query
            sections: List of section dictionaries from Stage 2
            topic_statistics: Optional statistics about the topic for the introduction

        Returns:
            Dictionary with integrated text and metadata
        """
        # Strip long citation IDs to short numeric placeholders before sending to LLM.
        # This prevents the LLM from corrupting complex IDs during narrative rewriting.
        stripped_sections, citation_mapping = self._strip_citations(sections)

        # Build sections text using stripped content
        sections_text = self._build_sections_text(stripped_sections)
        stats_text = self._format_statistics(topic_statistics)

        user_prompt = f"""Domanda: {query}

{stats_text}
Sezioni:
{sections_text}

Crea documento CONCISO con Introduzione (2-3 frasi che NOMINANO il provvedimento specifico e citano le STATISTICHE fornite sopra) + sezioni per coalizione.

⚠️ CRITICO:
1. Copia ESATTAMENTE ogni {{CIT:N}} carattere per carattere - NON modificare i numeri!
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
                temperature=0.0,
                max_tokens=5000
            )

            integrated_text = response.choices[0].message.content

            # Restore original long citation IDs from numeric placeholders
            integrated_text = self._restore_citations(integrated_text, citation_mapping)

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

    def _get_section_by_party(self, sections: List[Dict[str, Any]], party: str) -> str:
        """Get content for a specific party from sections."""
        for section in sections:
            if section.get("party") == party:
                return section.get("content", "")
        return ""

    def _build_sections_text(self, sections: List[Dict[str, Any]]) -> str:
        """Build text from all sections, grouped by coalition.

        Uses [BLOCCO: ...] markers instead of ## markdown headers to prevent
        the integrator LLM from confusing INPUT structure with the OUTPUT
        headers it must generate, which causes duplicate section headers.
        """
        parts = []

        # Government first if present
        gov_content = self._get_section_by_party(sections, "GOVERNO")
        if gov_content:
            parts.append("[BLOCCO: GOVERNO]\n" + gov_content)

        # Maggioranza sections
        magg_parts = []
        for party in self.MAGGIORANZA:
            content = self._get_section_by_party(sections, party)
            if content:
                magg_parts.append(f"[PARTITO: {party}]\n{content}")
        if magg_parts:
            parts.append("[BLOCCO: MAGGIORANZA]\n" + "\n\n".join(magg_parts))

        # Opposizione sections
        opp_parts = []
        for party in self.OPPOSIZIONE:
            content = self._get_section_by_party(sections, party)
            if content:
                opp_parts.append(f"[PARTITO: {party}]\n{content}")
        if opp_parts:
            parts.append("[BLOCCO: OPPOSIZIONE]\n" + "\n\n".join(opp_parts))

        return "\n\n---\n\n".join(parts)

    def _simple_concatenation(self, sections: List[Dict[str, Any]]) -> str:
        """Simple fallback concatenation without LLM integration, grouped by coalition."""
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
                magg_parts.append(f"Per {party}, " + strip_party_header(content))
        if magg_parts:
            parts.append("## Posizioni della Maggioranza\n\n" + "\n\n".join(magg_parts))

        # Opposizione sections
        opp_parts = []
        for party in self.OPPOSIZIONE:
            content = self._get_section_by_party(sections, party)
            if content:
                opp_parts.append(f"Per {party}, " + strip_party_header(content))
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
        registry: Optional['CitationRegistry'] = None,
        topic_statistics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Integrate with citation guard.

        Verifies citation preservation pre and post integration.
        Retries with stricter prompt if citations are corrupted.

        Args:
            query: Original user query
            sections: List of section dictionaries from Stage 2
            registry: Optional CitationRegistry for tracking
            topic_statistics: Optional statistics about the topic for the introduction

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
        result = self.integrate(query, sections, topic_statistics=topic_statistics)

        # Post-integration: verify citations preserved
        integrated_text = result.get("text", "")
        found_citations = set(re.findall(r'\[CIT:([^\]]+)\]', integrated_text))

        missing = expected_citations - found_citations
        retried = False

        if missing:
            logger.warning(f"Integrator corrupted {len(missing)} citations: {list(missing)}")
            for cit_id in missing:
                sentence = citation_sentences.get(cit_id, "").replace("\n", " ")
                logger.debug(f"  [CORRUPT] [{cit_id}] context: {sentence[:200]!r}")

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
