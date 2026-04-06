"""
Direct single-prompt generation for multi-view parliamentary summarization.

Replaces the 4-stage pipeline (Analyst → Sectional → Integrator → Surgeon)
with a single LLM call. Python handles evidence selection and citation
verification; the LLM only writes the narrative.

Design principles:
- Evidence pre-selection in Python (top speaker + best chunk per party)
- Single LLM call with structured output
- Deterministic citation verification (no LLM-based surgeon)
- Same output format as the 4-stage pipeline
"""
import logging
import re
import time
from collections import Counter, defaultdict
from datetime import date as date_type
from typing import Any, Dict, List, Optional

from ...config import get_config
from ...key_pool import make_client
from ..citation.sentence_extractor import compute_chunk_salience

logger = logging.getLogger(__name__)

# Bridge verbs for citation integration — each party gets a unique one
_BRIDGE_VERBS = [
    "afferma che", "dichiara che", "sostiene che", "sottolinea che",
    "evidenzia che", "rileva che", "osserva che", "denuncia che",
    "critica il fatto che", "puntualizza che", "lamenta che",
    "chiede conto di", "rivendica che", "propone che",
]


class DirectWriter:
    """Single-prompt multi-view parliamentary summarizer."""

    def __init__(self):
        self.config = get_config()
        config_data = self.config.load_config()
        gen_config = config_data.get("generation", {})
        self.model = gen_config.get("models", {}).get("writer", "gpt-4.1-mini")
        self.client = make_client()
        self.enable_synthesis = gen_config.get("enable_synthesis", True)

    async def generate(
        self,
        query: str,
        evidence_list: List[Dict[str, Any]],
        stream_callback: Optional[callable] = None,
        locale: str = "it",
    ) -> Dict[str, Any]:
        """
        Generate multi-view summary in a single LLM call.

        Returns same shape as GenerationPipeline.generate() for drop-in replacement.
        """
        start = time.perf_counter()

        # --- Step 1: Pre-process evidence (Python, no LLM) ---
        government_evidence = self._get_government_evidence(evidence_list)
        evidence_by_party = self._group_evidence_by_party(evidence_list)
        topic_stats = self._compute_topic_statistics(evidence_list)

        # Select top speaker + best chunk per party
        party_selections = self._select_per_party(evidence_by_party)
        gov_selection = self._select_government(government_evidence)

        # Debug: log evidence distribution
        parties_with_ev = {p: len(v) for p, v in evidence_by_party.items() if v}
        logger.info(
            "[DIRECT] Evidence distribution: %d gov, %d party chunks across %s",
            len(government_evidence),
            sum(len(v) for v in evidence_by_party.values()),
            parties_with_ev or "NO PARTIES",
        )
        # Debug: sample first 5 evidence dicts to see actual field values
        for i, e in enumerate(evidence_list[:5]):
            logger.info(
                "[DIRECT] Evidence[%d]: coalition=%s, speaker_role=%s, party=%s, speaker=%s",
                i, e.get("coalition"), e.get("speaker_role"), e.get("party"), e.get("speaker_name"),
            )

        if stream_callback:
            await stream_callback({
                "type": "progress",
                "stage": 1,
                "message": "Preparing multi-view summary...",
            })

        # --- Step 2: Build prompt with pre-selected evidence ---
        system_prompt = self._build_system_prompt(locale=locale)
        user_prompt = self._build_user_prompt(
            query, gov_selection, party_selections, topic_stats
        )

        if stream_callback:
            await stream_callback({
                "type": "progress",
                "stage": 2,
                "message": "Writing multi-view sections...",
            })

        # --- Step 3: Single LLM call ---
        logger.info(
            "[DIRECT] Calling %s — %d parties with evidence, gov=%s",
            self.model,
            sum(1 for p in party_selections.values() if p),
            "yes" if gov_selection else "no",
        )

        import asyncio
        response = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.15,
                max_tokens=5000,
            ),
        )

        raw_text = response.choices[0].message.content or ""
        elapsed_llm = time.perf_counter() - start

        logger.info("[DIRECT] LLM response: %d chars in %.1fs", len(raw_text), elapsed_llm)
        # Log first 500 chars to debug citation format
        logger.info("[DIRECT] Text sample: %s", raw_text[:500].replace('\n', '\\n'))

        if stream_callback:
            await stream_callback({
                "type": "progress",
                "stage": 3,
                "message": "Verifying citations...",
            })

        # --- Step 4: Post-process — verify citations, build metadata ---
        text, citations, extra_ids = self._resolve_citations(
            raw_text, gov_selection, party_selections, evidence_list
        )

        elapsed_total = time.perf_counter() - start
        logger.info(
            "[DIRECT] Complete: %d citations, %.1fs total (LLM: %.1fs)",
            len(citations), elapsed_total, elapsed_llm,
        )

        return {
            "text": text,
            "citations": citations,
            "extra_citation_ids": extra_ids,
            "topic_statistics": topic_stats,
            "metadata": {
                "generation_mode": "direct",
                "model": self.model,
                "elapsed_s": round(elapsed_total, 2),
                "llm_elapsed_s": round(elapsed_llm, 2),
            },
        }

    # ── System prompt ──────────────────────────────────────────────────

    def _build_system_prompt(self, locale: str = "it") -> str:
        if locale == "en":
            return self._system_prompt_en()
        return self._system_prompt_it()

    def _system_prompt_it(self) -> str:
        return """Sei un analista parlamentare esperto. Scrivi una sintesi multi-view delle posizioni dei gruppi parlamentari su un tema, basandoti ESCLUSIVAMENTE sulle evidenze fornite.

## STRUTTURA

## Introduzione

2-3 frasi con dati concreti: nome del provvedimento, numero di interventi, numero di deputati coinvolti, arco temporale, numeri delle sedute.

## Posizione del Governo

Se presente: 1 paragrafo con citazione del ministro competente.

## Posizioni della Maggioranza

Per ogni partito con evidenze, un paragrafo fluido. Esempio:

Per Fratelli d'Italia, il gruppo esprime critiche nei confronti del PNRR sottolineando le difficoltà burocratiche. **Deidda** critica il fatto che «ecco i progetti del PNRR, questo bellissimo PNRR che è passato in una giornata e mezzo con la fiducia». Il partito chiede una revisione che tenga conto delle specificità territoriali.

## Posizioni dell'Opposizione

Stesso formato dei partiti di maggioranza.

## REGOLE DI SCRITTURA

1. CITAZIONE VERBATIM: Copia ESATTAMENTE il testo dalla CITAZIONE DA USARE. Non modificare nulla. Il testo va tra «guillemets».

2. INTEGRAZIONE FLUIDA della citazione: la frase che introduce la citazione deve essere coerente con il contenuto citato.
   - Se la citazione è una domanda retorica, USA verbi come "si domanda", "chiede", "si interroga" — NON "afferma che".
   - Se la citazione è un'affermazione, usa "sostiene che", "dichiara che", "afferma che".
   - Se la citazione è una critica, usa "critica il fatto che", "denuncia che".

3. COGNOMI OBBLIGATORI: OGNI sezione partito DEVE contenere il cognome dello speaker in **grassetto** prima del verbo. Formato: **Cognome** verbo che «citazione». MAI scrivere solo il nome del partito senza il cognome dello speaker.

4. VERBI TUTTI DIVERSI: Ogni sezione usa un verbo introduttivo diverso. Mai ripetere lo stesso verbo nel documento.

5. NOMI DEI PARTITI: Usa il nome completo solo la prima volta. NON ripetere "partito di maggioranza" o "partito di opposizione" — è ridondante perché sono già sotto l'header della sezione.

6. PARTITI SENZA EVIDENZE: "Per [Partito], nel corpus analizzato non risultano interventi rilevanti su questo tema."

7. LUNGHEZZA: 3-5 frasi per partito. Bilanciare maggioranza e opposizione.

8. NON INVENTARE: Nessuna informazione non presente nelle evidenze."""

    def _system_prompt_en(self) -> str:
        return """You are an expert parliamentary analyst. Write a multi-view summary of parliamentary group positions on a topic, based EXCLUSIVELY on the provided evidence.

CRITICAL: Write narrative text in English. Citations between «guillemets» MUST stay in ORIGINAL ITALIAN — NEVER translate them. Copy them exactly as provided.

## STRUCTURE

## Introduction

2-3 sentences with concrete data: name of the measure, number of interventions, number of deputies involved, time span, session numbers.

## Government Position

If present: 1 paragraph with a citation from the competent minister.

## Majority Positions

For each majority party with evidence, one fluid paragraph. Example:

For Fratelli d'Italia, the group criticizes the PNRR implementation, highlighting bureaucratic difficulties. **Deidda** criticizes the fact that «ecco i progetti del PNRR, questo bellissimo PNRR che è passato in una giornata e mezzo con la fiducia». The party calls for a revision that takes into account local specificities.

NOTE: In the example above, the citation «ecco i progetti...» is in ITALIAN. This is correct. ALL citations must remain in Italian.

## Opposition Positions

Same format as majority parties.

## WRITING RULES

1. CITATIONS IN ORIGINAL ITALIAN: The text between «» MUST be copied EXACTLY from the PROVIDED CITATION without any translation. The citations are Italian parliamentary speech — they MUST remain in Italian. Only the surrounding narrative is in English.

2. FLUID INTEGRATION: the introductory sentence must be coherent with the cited content.
   - Rhetorical question → "questions whether", "asks", "wonders"
   - Statement → "argues that", "declares that", "states that"
   - Criticism → "criticizes the fact that", "denounces that"

3. MANDATORY SURNAMES: EVERY party section MUST include the speaker's surname in **bold** before the verb. Format: **Surname** verb «citation». NEVER write just the party name without the speaker's surname.

4. ALL DIFFERENT VERBS: Each section uses a different introductory verb. Never repeat.

5. PARTIES WITHOUT EVIDENCE: "For [Party], no relevant interventions on this topic were found in the analyzed corpus."

6. LENGTH: 3-5 sentences per party. Balance majority and opposition.

7. DO NOT INVENT: No information not present in the evidence."""

    # ── User prompt builder ────────────────────────────────────────────

    def _build_user_prompt(
        self,
        query: str,
        gov_selection: Optional[Dict[str, Any]],
        party_selections: Dict[str, Optional[Dict[str, Any]]],
        topic_stats: Dict[str, Any],
    ) -> str:
        config_data = self.config.load_config()
        coalitions = config_data.get("coalitions", {})
        maggioranza_parties = set(coalitions.get("maggioranza", []))
        opposizione_parties = set(coalitions.get("opposizione", []))

        parts = [f"## Query\n{query}\n"]

        # Topic statistics for introduction
        parts.append("## Statistiche")
        parts.append(f"- Interventi analizzati: {topic_stats.get('intervention_count', 0)}")
        parts.append(f"- Deputati coinvolti: {topic_stats.get('speaker_count', 0)}")
        if topic_stats.get("first_date"):
            parts.append(f"- Periodo: {topic_stats['first_date']} — {topic_stats.get('last_date', '')}")
        if topic_stats.get("debate_title"):
            parts.append(f"- Provvedimento principale: {topic_stats['debate_title']}")
        sessions = topic_stats.get("sessions_detail", [])
        if sessions:
            nums = [str(s.get("session_number", "")) for s in sessions[:10] if s.get("session_number")]
            if nums:
                parts.append(f"- Sedute: N. {', '.join(nums)}")
        parts.append("")

        # Government evidence
        parts.append("## GOVERNO")
        if gov_selection:
            parts.append(self._format_evidence_block(gov_selection, is_gov=True))
        else:
            parts.append("NESSUNA EVIDENZA da ministri competenti sul tema.\n")

        # Majority parties
        verb_idx = 0
        parts.append("## MAGGIORANZA")
        for party in sorted(maggioranza_parties):
            sel = party_selections.get(party)
            parts.append(f"### {party}")
            if sel:
                verb = _BRIDGE_VERBS[verb_idx % len(_BRIDGE_VERBS)]
                parts.append(f"Verbo da usare: {verb}")
                parts.append(self._format_evidence_block(sel))
                verb_idx += 1
            else:
                parts.append("NESSUNA EVIDENZA\n")

        # Opposition parties
        parts.append("## OPPOSIZIONE")
        for party in sorted(opposizione_parties):
            sel = party_selections.get(party)
            parts.append(f"### {party}")
            if sel:
                verb = _BRIDGE_VERBS[verb_idx % len(_BRIDGE_VERBS)]
                parts.append(f"Verbo da usare: {verb}")
                parts.append(self._format_evidence_block(sel))
                verb_idx += 1
            else:
                parts.append("NESSUNA EVIDENZA\n")

        return "\n".join(parts)

    def _format_evidence_block(self, sel: Dict[str, Any], is_gov: bool = False) -> str:
        """Format a pre-selected evidence block for the prompt."""
        e = sel["evidence"]
        lines = [
            f"- Speaker: {e.get('speaker_name', 'Sconosciuto')}",
        ]
        if not is_gov:
            lines.append(f"- Partito: {e.get('party', '')}")
        else:
            lines.append(f"- Ruolo: Membro del Governo")
        lines.extend([
            f"- Data: {e.get('date', '')}",
            f"- Seduta: {e.get('session_number', '')}",
            f"- Dibattito: {e.get('debate_title', '')}",
        ])

        # Add reported speech warning
        rs = e.get("reported_speech", {})
        if rs and rs.get("has_reported_speech"):
            lines.append("⚠️ ATTENZIONE: Contiene discorso riportato")

        # Add candidate quotes — LLM picks the best one
        candidates = sel.get("candidate_quotes", [])
        if len(candidates) == 1:
            lines.append(f"\nCITAZIONE DA USARE (copiare ESATTAMENTE):\n«{candidates[0]}»\n")
        elif candidates:
            lines.append("\nSCEGLI UNA di queste citazioni (copiare ESATTAMENTE):")
            for i, q in enumerate(candidates, 1):
                lines.append(f"  {i}. «{q}»")
            lines.append("")
        else:
            lines.append("\nNessuna citazione disponibile.\n")

        return "\n".join(lines)

    # ── Evidence selection (Python, no LLM) ────────────────────────────

    def _select_per_party(
        self, evidence_by_party: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Select best speaker + best quote for each party."""
        selections = {}
        for party, chunks in evidence_by_party.items():
            if not chunks:
                selections[party] = None
                continue

            # Take top chunk (already sorted by authority-first interleaving)
            best = chunks[0]

            # Skip if reported speech in opening
            rs = best.get("reported_speech", {})
            if rs and rs.get("opening_is_reported"):
                # Try next chunk
                for alt in chunks[1:]:
                    alt_rs = alt.get("reported_speech", {})
                    if not (alt_rs and alt_rs.get("opening_is_reported")):
                        best = alt
                        break

            # Extract candidate quotes for the LLM to choose from
            candidates = self._extract_candidate_quotes(best)

            selections[party] = {
                "evidence": best,
                "candidate_quotes": candidates,
                "selected_quote": candidates[0] if candidates else "",
            }

            logger.debug(
                "[DIRECT] %s → %s (auth=%.2f, sim=%.2f, %d candidates)",
                party,
                best.get("speaker_name", "?"),
                best.get("authority_score", 0),
                best.get("similarity", 0),
                len(candidates),
            )

        return selections

    def _select_government(
        self, gov_evidence: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select the most topic-relevant government speaker (minister).

        Government members are selected by topic relevance (similarity),
        NOT by party authority. They represent the government as a whole,
        not their original party.
        """
        if not gov_evidence:
            return None

        # Sort by similarity to query (topic relevance) — NOT authority
        gov_sorted = sorted(
            gov_evidence,
            key=lambda e: e.get("similarity", 0),
            reverse=True,
        )
        best = gov_sorted[0]
        candidates = self._extract_candidate_quotes(best)

        logger.info(
            "[DIRECT] Gov speaker: %s (similarity=%.2f, role=%s)",
            best.get("speaker_name", "?"),
            best.get("similarity", 0),
            best.get("debate_title", ""),
        )

        return {
            "evidence": best,
            "candidate_quotes": candidates,
            "selected_quote": candidates[0] if candidates else "",
        }

    def _extract_candidate_quotes(self, evidence: Dict[str, Any]) -> List[str]:
        """Extract up to 3 candidate quote sentences from a chunk.

        Filters out procedural text, keeps only declarative/substantive
        sentences under 200 chars each. The LLM picks the best one.
        """
        text = evidence.get("chunk_text", "") or evidence.get("quote_text", "")
        if not text:
            return []

        # Split into sentences
        sentences = re.split(r'(?<=[.!?»])\s+', text.strip())
        if not sentences:
            return [text[:200]]

        # Filter: remove procedural, too short, too long
        candidates = []
        for s in sentences:
            s = s.strip()
            if len(s) < 30 or len(s) > 250:
                continue
            low = s.lower()
            # Skip procedural openers
            if low.startswith(("presidente,", "grazie,", "onorevol",
                              "signor presidente", "colleghi,")):
                continue
            # Skip pure procedural phrases
            if any(w in low for w in ("ordine del giorno", "metto in votazione",
                                       "è così esaurit", "passiamo al")):
                continue
            candidates.append(s)

        if not candidates:
            # Fallback: take best sentence regardless
            candidates = [s.strip() for s in sentences if len(s.strip()) > 30]

        # Return top 3 candidates (first ones tend to be most relevant in a chunk)
        return candidates[:3]

    # ── Citation verification (Python, no LLM) ────────────────────────

    def _resolve_citations(
        self,
        text: str,
        gov_selection: Optional[Dict[str, Any]],
        party_selections: Dict[str, Optional[Dict[str, Any]]],
        evidence_list: List[Dict[str, Any]],
    ) -> tuple:
        """Match «guillemets» quotes in LLM output to pre-selected evidence chunks.

        The LLM writes «verbatim quote» and Python matches each to its chunk_id,
        converting to markdown links: [«quote»](chunk_id).

        Returns (final_text, citations_list, extra_citation_ids).
        """
        # Build lookup: all pre-selected evidence keyed by normalized quote substring
        selections = {}
        if gov_selection:
            selections["__gov__"] = gov_selection
        for party, sel in party_selections.items():
            if sel:
                selections[party] = sel

        citations = []

        # Find all «...» in text
        guillemet_pattern = r'«([^»]+)»'

        def _replace_quote(match):
            quoted = match.group(1)
            norm_quoted = " ".join(quoted.split()).lower()

            # Find which pre-selected evidence this quote came from
            best_sel = None
            best_overlap = 0

            for key, sel in selections.items():
                # Check against ALL candidate quotes, not just the first
                all_sources = sel.get("candidate_quotes", [])
                if not all_sources and sel.get("selected_quote"):
                    all_sources = [sel["selected_quote"]]
                # Also check the full chunk text
                chunk_text = sel["evidence"].get("chunk_text", "")

                for source in all_sources:
                    norm_source = " ".join(source.split()).lower()
                    if norm_quoted in norm_source or norm_source in norm_quoted:
                        overlap = min(len(norm_quoted), len(norm_source))
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_sel = sel

                # Also match against full chunk text (LLM may quote different part)
                if not best_sel and chunk_text:
                    norm_chunk = " ".join(chunk_text.split()).lower()
                    if norm_quoted in norm_chunk:
                        best_sel = sel
                        best_overlap = len(norm_quoted)

            if not best_sel:
                # Fuzzy: first 40 chars
                for key, sel in selections.items():
                    all_sources = sel.get("candidate_quotes", [sel.get("selected_quote", "")])
                    for source in all_sources:
                        norm_source = " ".join(source.split()).lower()
                        if norm_quoted[:40] in norm_source or norm_source[:40] in norm_quoted:
                            best_sel = sel
                            break
                    if best_sel:
                        break

            if best_sel:
                ev = best_sel["evidence"]
                chunk_id = ev.get("evidence_id", "")

                session_date = ev.get("date", "")
                if hasattr(session_date, "strftime"):
                    session_date = session_date.strftime("%Y-%m-%d")
                elif hasattr(session_date, "to_native"):
                    session_date = str(session_date.to_native())

                # Avoid duplicate citations
                if not any(c["evidence_id"] == chunk_id for c in citations):
                    citations.append({
                        "evidence_id": chunk_id,
                        "quote_text": quoted,
                        "speaker_name": ev.get("speaker_name", ""),
                        "party": ev.get("party", ""),
                        "date": str(session_date),
                    })

                logger.info("[DIRECT] ✓ Matched citation: %s → %s", quoted[:50], chunk_id)
                # Convert to markdown link for frontend
                return f"[«{quoted}»]({chunk_id})"
            else:
                logger.warning("[DIRECT] ✗ Unmatched quote: %s", quoted[:60])
                return f"«{quoted}»"

        text = re.sub(guillemet_pattern, _replace_quote, text)

        logger.info("[DIRECT] Citations resolved: %d matched", len(citations))

        return text, citations, []

    # ── Evidence grouping (reused from pipeline) ──────────────────────

    def _group_evidence_by_party(
        self, evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group evidence by party with authority-first interleaving."""
        all_parties = self.config.get_all_parties()
        by_party: Dict[str, List[Dict[str, Any]]] = {p: [] for p in all_parties}

        # Load group aliases for historical/variant name resolution
        config_data = self.config.load_config()
        aliases_raw = config_data.get("group_aliases", {})
        # Build case-insensitive alias lookup
        aliases = {k.upper(): v for k, v in aliases_raw.items()}

        gov_count = 0
        for evidence in evidence_list:
            if evidence.get("speaker_role") == "GovernmentMember":
                gov_count += 1
                continue
            party = (
                evidence.get("current_party")
                if evidence.get("party_changed") and evidence.get("current_party")
                else evidence.get("party", "Misto")
            )
            # Resolve aliases (historical/variant group names → canonical)
            canonical = aliases.get(party.upper()) if party else None
            if canonical:
                party = canonical

            if party not in by_party:
                # Try case-insensitive match
                matched = False
                for known in all_parties:
                    if party.upper() == known.upper():
                        by_party[known].append(evidence)
                        matched = True
                        break
                if not matched:
                    logger.warning("[DIRECT] Unmatched party '%s' → Misto", party)
                    by_party["Misto"].append(evidence)
            else:
                by_party[party].append(evidence)

        logger.info(
            "[DIRECT] _group_evidence_by_party: %d total, %d gov filtered, parties: %s",
            len(evidence_list), gov_count,
            {p: len(v) for p, v in by_party.items() if v},
        )

        # Speaker-first interleaving sort
        for party in by_party:
            chunks = by_party[party]
            if not chunks:
                continue

            for e in chunks:
                if e.get("salience") is None:
                    text = e.get("chunk_text") or e.get("quote_text", "")
                    e["salience"] = compute_chunk_salience(text)

            speaker_chunks: Dict[str, list] = defaultdict(list)
            for e in chunks:
                speaker_chunks[e.get("speaker_id", "")].append(e)

            def _chunk_quality(e):
                return 0.75 * e.get("similarity", 0.0) + 0.25 * (e.get("salience") or 0.0)

            for sid in speaker_chunks:
                speaker_chunks[sid].sort(key=_chunk_quality, reverse=True)

            def _speaker_rank(sid):
                auth = speaker_chunks[sid][0].get("authority_score", 0.0)
                best = _chunk_quality(speaker_chunks[sid][0])
                return 0.70 * auth + 0.30 * best

            sorted_speakers = sorted(speaker_chunks.keys(), key=_speaker_rank, reverse=True)

            max_depth = max(len(v) for v in speaker_chunks.values())
            interleaved = []
            for depth in range(max_depth):
                for sid in sorted_speakers:
                    evs = speaker_chunks[sid]
                    if depth < len(evs):
                        interleaved.append(evs[depth])

            by_party[party] = interleaved

        return by_party

    def _get_government_evidence(
        self, evidence_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract government member evidence (GovernmentMember label in Neo4j)."""
        return [e for e in evidence_list if e.get("speaker_role") == "GovernmentMember"]

    def _compute_topic_statistics(
        self, evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute topic statistics for introduction and frontend."""
        if not evidence_list:
            return {
                "intervention_count": 0,
                "speaker_count": 0,
                "first_date": None,
                "last_date": None,
                "debate_title": None,
                "speakers_detail": [],
                "interventions_detail": [],
                "sessions_detail": [],
            }

        unique_speeches = set(
            e.get("speech_id") for e in evidence_list if e.get("speech_id")
        )
        unique_speakers = set(
            e.get("speaker_id") for e in evidence_list if e.get("speaker_id")
        )
        dates = [e.get("date") for e in evidence_list if e.get("date")]

        debate_titles = [
            e.get("debate_title") for e in evidence_list if e.get("debate_title")
        ]
        most_common_title = (
            Counter(debate_titles).most_common(1)[0][0] if debate_titles else None
        )

        session_numbers = [
            e.get("session_number") for e in evidence_list if e.get("session_number")
        ]

        # Build speaker details
        speakers_by_id: Dict[str, Dict[str, Any]] = {}
        for e in evidence_list:
            sid = e.get("speaker_id", "")
            if sid and sid not in speakers_by_id:
                speakers_by_id[sid] = {
                    "speaker_id": sid,
                    "speaker_name": e.get("speaker_name", ""),
                    "party": e.get("party", ""),
                    "speaker_role": e.get("speaker_role", "Deputy"),
                    "intervention_count": 0,
                }
            if sid:
                speakers_by_id[sid]["intervention_count"] += 1

        # Build intervention details (unique speeches)
        seen_speeches = set()
        interventions_detail = []
        for e in evidence_list:
            speech_id = e.get("speech_id", "")
            if speech_id and speech_id not in seen_speeches:
                seen_speeches.add(speech_id)
                session_date = e.get("date", "")
                if hasattr(session_date, "strftime"):
                    session_date = session_date.strftime("%Y-%m-%d")
                interventions_detail.append({
                    "speech_id": speech_id,
                    "speaker_name": e.get("speaker_name", ""),
                    "party": e.get("party", ""),
                    "date": str(session_date),
                    "debate_title": e.get("debate_title", ""),
                })

        # Build session details
        seen_sessions = set()
        sessions_detail = []
        for e in evidence_list:
            snum = e.get("session_number")
            if snum and snum not in seen_sessions:
                seen_sessions.add(snum)
                session_date = e.get("date", "")
                if hasattr(session_date, "strftime"):
                    session_date = session_date.strftime("%Y-%m-%d")
                sessions_detail.append({
                    "session_number": snum,
                    "date": str(session_date),
                })

        # Sort dates
        parsed_dates = []
        for d in dates:
            if hasattr(d, "year"):
                parsed_dates.append(d)
            elif isinstance(d, str) and d:
                try:
                    from datetime import datetime
                    parsed_dates.append(datetime.strptime(d, "%Y-%m-%d").date())
                except ValueError:
                    pass

        first_date = min(parsed_dates) if parsed_dates else None
        last_date = max(parsed_dates) if parsed_dates else None

        return {
            "intervention_count": len(unique_speeches),
            "speaker_count": len(unique_speakers),
            "first_date": first_date,
            "last_date": last_date,
            "debate_title": most_common_title,
            "speakers_detail": list(speakers_by_id.values()),
            "interventions_detail": interventions_detail,
            "sessions_detail": sorted(sessions_detail, key=lambda s: s.get("session_number", 0)),
        }
