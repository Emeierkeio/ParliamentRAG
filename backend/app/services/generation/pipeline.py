"""
4-Stage Generation Pipeline Orchestrator.

Coordinates:
1. Analyst - Claim decomposition
2. Sectional Writer - Per-party sections
3. Narrative Integrator - Coherence
4. Citation Surgeon - Verbatim citations

Includes citation integrity system:
- Citation Registry: tracks citations through pipeline
- Coherence Validator: verifies semantic alignment
- Integrator Guard: prevents citation loss during integration
- Final Completeness Check: ensures all citations resolved
"""
import re
import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime

from .analyst import ClaimAnalyst
from .sectional import SectionalWriter
from .integrator import NarrativeIntegrator
from .surgeon import CitationSurgeon
from .synthesis import ConvergenceDivergenceAnalyzer
from .citation_registry import CitationRegistry
from .coherence_validator import CoherenceValidator
from ...config import get_config

logger = logging.getLogger(__name__)


class GenerationPipeline:
    """
    Orchestrates the 4-stage generation pipeline with citation integrity.

    Stage 1 (Analyst): Query → Atomic claims with evidence requirements
    Stage 2 (Sectional): Claims + Evidence → Per-party sections
    Stage 3 (Integrator): Sections → Coherent narrative (with guard)
    Stage 4 (Surgeon): Narrative → Final text with verbatim citations

    Citation Integrity System:
    - Registry: Tracks all citations through the pipeline
    - Coherence Validator: Ensures semantic alignment
    - Integrator Guard: Prevents citation loss
    - Final Check: Verifies all citations resolved
    """

    def __init__(self):
        self.config = get_config()
        config_data = self.config.load_config()
        integrity_config = config_data.get("citation", {}).get("integrity", {})

        gen_config = config_data.get("generation", {})
        self.enable_synthesis = gen_config.get("enable_synthesis", True)

        self.analyst = ClaimAnalyst()
        self.sectional_writer = SectionalWriter()
        self.integrator = NarrativeIntegrator()
        self.surgeon = CitationSurgeon()
        self.synthesis_analyzer = ConvergenceDivergenceAnalyzer()
        self.coherence_validator = CoherenceValidator(
            min_coherence_score=integrity_config.get("min_coherence_score", 0.6),
            method=integrity_config.get("coherence_method", "embedding"),
        )

    async def generate(
        self,
        query: str,
        evidence_list: List[Dict[str, Any]],
        stream_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Run the complete generation pipeline with citation integrity.

        Args:
            query: User query
            evidence_list: Retrieved evidence
            stream_callback: Optional callback for streaming progress

        Returns:
            Complete response with text, citations, metadata, and integrity report
        """
        start_time = datetime.now()
        pipeline_metadata = {
            "stages": {},
            "start_time": start_time.isoformat(),
            "citation_integrity": {}
        }

        # Initialize Citation Registry for tracking
        registry = CitationRegistry()
        registry.register_evidence(evidence_list)

        # === Stage 1: Analyst ===
        if stream_callback:
            await stream_callback({
                "type": "progress",
                "stage": 1,
                "message": "Analyzing query and evidence..."
            })

        claims_result = self.analyst.analyze(query, evidence_list)
        claims = claims_result.get("claims", [])

        pipeline_metadata["stages"]["analyst"] = {
            "claims_count": len(claims),
            "query_type": claims_result.get("query_type"),
            "requires_government": claims_result.get("requires_government_view", False),
        }

        logger.info(f"Stage 1 complete: {len(claims)} claims identified")

        # === Prepare evidence by party ===
        evidence_by_party = self._group_evidence_by_party(evidence_list)
        government_evidence = self._get_government_evidence(evidence_list)

        # Build evidence map for surgeon
        evidence_map = {
            e.get("evidence_id"): e for e in evidence_list if e.get("evidence_id")
        }

        # === Stage 2: Sectional Writer ===
        if stream_callback:
            await stream_callback({
                "type": "progress",
                "stage": 2,
                "message": "Writing party sections..."
            })

        sections = []
        async for section in self.sectional_writer.write_sections(
            query=query,
            claims=claims,
            evidence_by_party=evidence_by_party,
            government_evidence=government_evidence
        ):
            sections.append(section)

            # Register citation bindings in registry
            content = section.get("content", "")
            party = section.get("party", "")
            citation_ids = re.findall(r'\[CIT:([^\]]+)\]', content)
            for cit_id in citation_ids:
                # Extract intro text (text before [CIT:id])
                pattern = rf'([^.!?]*)\[CIT:{re.escape(cit_id)}\]'
                match = re.search(pattern, content)
                intro = match.group(1).strip() if match else ""
                registry.bind_citation(cit_id, party, intro)

            if stream_callback:
                await stream_callback({
                    "type": "section",
                    "party": party,
                    "has_evidence": section.get("has_evidence", False),
                })

        pipeline_metadata["stages"]["sectional"] = {
            "sections_count": len(sections),
            "parties_with_evidence": sum(1 for s in sections if s.get("has_evidence")),
            "citations_bound": len(registry.get_expected_citations()),
        }

        logger.info(f"Stage 2 complete: {len(sections)} sections written, "
                    f"{len(registry.get_expected_citations())} citations bound")

        # === Stage 3: Narrative Integrator with Guard ===
        if stream_callback:
            await stream_callback({
                "type": "progress",
                "stage": 3,
                "message": "Integrating narrative..."
            })

        # Compute topic statistics for the introduction
        topic_statistics = self._compute_topic_statistics(evidence_list)

        # Use integrate_with_guard to verify citation preservation
        integrated = self.integrator.integrate_with_guard(
            query, sections, registry, topic_statistics=topic_statistics
        )

        pipeline_metadata["stages"]["integrator"] = {
            "integration_success": not integrated.get("integration_failed", False),
            "citation_verification": integrated.get("citation_verification", {}),
            "citations_repaired": integrated.get("citations_repaired", 0),
        }

        logger.info(f"Stage 3 complete: Narrative integrated, "
                    f"{integrated.get('citations_repaired', 0)} citations repaired")

        # === Post-Integration: Balance Check (Coverage-based Fairness) ===
        balance_info = self._check_coalition_balance(integrated.get("text", ""))
        pipeline_metadata["stages"]["balance"] = balance_info
        if balance_info.get("balance_warning"):
            logger.warning(
                f"Coalition imbalance detected: "
                f"majority={balance_info['majority_words']} words, "
                f"opposition={balance_info['opposition_words']} words, "
                f"ratio={balance_info['ratio']:.1f}:1"
            )

        # Stage 3.5 (Convergence-Divergence Analysis) removed

        # === Pre-Surgeon: Coherence Validation ===
        coherence_report = self.coherence_validator.validate_all_citations(
            integrated.get("text", ""),
            evidence_map
        )

        pipeline_metadata["citation_integrity"]["coherence"] = {
            "all_coherent": coherence_report["all_coherent"],
            "coherent_count": coherence_report["coherent_citations"],
            "incoherent_count": coherence_report["incoherent_citations"],
            "average_score": coherence_report["average_score"],
        }

        integrated_text = integrated.get("text", "")

        if not coherence_report["all_coherent"]:
            incoherent = self.coherence_validator.get_incoherent_citations(coherence_report)
            logger.warning(f"Coherence issues: {len(incoherent)} incoherent citations")
            for ic in incoherent[:3]:  # Log first 3
                logger.warning(f"  - {ic.get('evidence_id')}: {ic.get('warning')}")

            # Hard-remove citations with extreme mismatch (likely wrong source cited)
            HARD_REMOVE_THRESHOLD = 0.35
            # For the most extreme mismatches, also rewrite the party paragraph
            # without any citation so the section remains coherent.
            REWRITE_THRESHOLD = 0.25
            hard_mismatches = [ic for ic in incoherent if ic.get("score", 1.0) < HARD_REMOVE_THRESHOLD]
            if hard_mismatches:
                logger.warning(f"Hard-removing {len(hard_mismatches)} citations with score < {HARD_REMOVE_THRESHOLD}")
                for ic in hard_mismatches:
                    eid = ic.get("evidence_id", "")
                    # Remove «inline quote» [CIT:id] together to prevent bare «» in output.
                    # Allow punctuation/whitespace between » and [CIT: (LLM may insert . or ,)
                    integrated_text = re.sub(
                        rf'«[^»]+»[.,;:!?\s]*\[CIT:{re.escape(eid)}\]',
                        '',
                        integrated_text
                    )
                    # Also remove bare [CIT:id] if no inline quote preceded it
                    integrated_text = re.sub(rf'\[CIT:{re.escape(eid)}\]', '', integrated_text)

                # Rewrite paragraphs for parties whose citation was extremely incoherent
                # (score < REWRITE_THRESHOLD). The original section was written around a
                # citation that is now gone, leaving disconnected intro/positioning sentences.
                extreme_mismatches = [ic for ic in hard_mismatches if ic.get("score", 1.0) < REWRITE_THRESHOLD]
                if extreme_mismatches:
                    rewrite_tasks = {}
                    for ic in extreme_mismatches:
                        eid = ic.get("evidence_id", "")
                        party = evidence_map.get(eid, {}).get("party", "")
                        if not party or party in rewrite_tasks:
                            continue
                        # Only rewrite if the party has no remaining [CIT:] in the text
                        remaining = re.findall(r'\[CIT:[^\]]+\]', integrated_text)
                        party_eids = {e.get("evidence_id") for e in evidence_by_party.get(party, [])}
                        has_other_citations = any(
                            r in party_eids for r in remaining
                        )
                        if has_other_citations:
                            logger.info(f"Skipping rewrite for '{party}': still has other citations")
                            continue
                        party_evidence = evidence_by_party.get(party, [])
                        if party_evidence:
                            rewrite_tasks[party] = party_evidence

                    if rewrite_tasks:
                        logger.info(f"Rewriting {len(rewrite_tasks)} citation-free paragraphs: {list(rewrite_tasks)}")
                        rewrite_results = await asyncio.gather(*[
                            self.sectional_writer.write_section_without_citation(
                                query=query,
                                party=party,
                                evidence=ev,
                                claims=claims,
                            )
                            for party, ev in rewrite_tasks.items()
                        ])
                        for party, new_body in zip(rewrite_tasks.keys(), rewrite_results):
                            if new_body:
                                integrated_text = self._replace_party_paragraph(
                                    integrated_text, party, new_body
                                )

        # Update registry with coherence scores
        for detail in coherence_report.get("details", []):
            eid = detail.get("evidence_id")
            score = detail.get("score", 0)
            registry.set_coherence_score(eid, score)

        # === Stage 4: Citation Surgeon ===
        if stream_callback:
            await stream_callback({
                "type": "progress",
                "stage": 4,
                "message": "Inserting citations..."
            })

        final_result = self.surgeon.insert_citations(
            text=integrated_text,
            evidence_map=evidence_map,
            query=query
        )

        # Update registry with resolution status
        for cit in final_result.get("citations", []):
            registry.mark_resolved(cit.get("evidence_id"), success=True)

        for cit in final_result.get("failed_citations", []):
            registry.mark_resolved(
                cit.get("evidence_id"),
                success=False,
                error=cit.get("reason")
            )

        pipeline_metadata["stages"]["surgeon"] = {
            "citations_inserted": final_result.get("total_citations", 0),
            "citations_failed": final_result.get("failed_count", 0),
        }

        logger.info(
            f"Stage 4 complete: {final_result.get('total_citations', 0)} citations inserted"
        )

        # === Final Verification ===
        final_text = final_result.get("text", "")

        # Collect citation IDs found in text but NOT in evidence_map.
        # These may be valid DB chunks the LLM cited from broader context
        # (e.g. sectional writer saw them but they weren't in the top-20 sidebar).
        # We pass them to the caller (chat.py) so it can verify them against
        # the DB and add them to the sidebar — instead of stripping them here.
        valid_evidence_ids = set(evidence_map.keys())
        all_text_ids = set(
            m[1] for m in re.findall(
                r'\[([^\]]+)\]\((leg1[89]_[^)]+)\)', final_text
            )
        )
        extra_citation_ids = list(all_text_ids - valid_evidence_ids)
        if extra_citation_ids:
            logger.info(
                f"Found {len(extra_citation_ids)} citation IDs in text not in "
                f"evidence_map — passing to caller for DB verification: "
                f"{extra_citation_ids[:5]}"
            )

        # === Post-Surgeon: Recover untracked citations ===
        # The Integrator LLM sometimes outputs direct markdown links
        # [«quote»](evidence_id) instead of [CIT:id] placeholders.
        # These bypass the Surgeon's regex and are NOT in the citations list.
        # Extract them here so the frontend can match clicks to metadata.
        tracked_ids = {
            c.get("evidence_id") for c in final_result.get("citations", [])
        }
        untracked_links = re.findall(
            r'\[([^\]]+)\]\((leg1[89]_[^)]+)\)', final_text
        )
        for display_text, eid in untracked_links:
            if eid not in tracked_ids and eid in evidence_map:
                evidence = evidence_map[eid]
                # Use raw quote_text from evidence (verbatim extraction from source),
                # NOT the display text which has been modified by _format_citation
                # (parenthetical removal, dangling words, lowercase, etc.).
                raw_quote = evidence.get("quote_text", "") or evidence.get("chunk_text", "")

                final_result.get("citations", []).append({
                    "evidence_id": eid,
                    "quote_text": raw_quote,
                    "speaker_name": evidence.get("speaker_name"),
                    "party": evidence.get("party"),
                    "date": str(evidence.get("date", "")),
                    "span_start": evidence.get("span_start", 0),
                    "span_end": evidence.get("span_end", 0),
                })
                tracked_ids.add(eid)
                registry.mark_resolved(eid, success=True)
                logger.info(
                    f"Recovered untracked citation: {eid} "
                    f"(quote: '{raw_quote[:60]}...')"
                )

        if len(tracked_ids) > final_result.get("total_citations", 0):
            recovered = len(tracked_ids) - final_result.get("total_citations", 0)
            logger.info(f"Recovered {recovered} untracked citations from final text")

        # Check for bare «» citations not wrapped in markdown links and remove them.
        # These can appear when hard-removed citations leave orphaned quotes (e.g. when
        # the integrator LLM moves [CIT:id] after a period, separating it from «»).
        bare_citations = re.findall(r'(?<!\[)«[^»]+»', final_text)
        if bare_citations:
            logger.warning(
                f"Found {len(bare_citations)} bare citations without markdown links: "
                f"{[c[:50] for c in bare_citations[:3]]}"
            )
            final_text = re.sub(r'(?<!\[)«[^»]+»', '', final_text)

        # Clean up verb-phrase artifacts left after removing a quote (bare or hard-removed).
        # Runs unconditionally because hard-removal (lines 235-241) strips «quote»[CIT:id]
        # but leaves attribution phrases like "**Lupi** afferma: ." intact — and since
        # no bare «» remain afterwards, the bare_citations block above never fires.
        #
        # Three artifact patterns, applied in order:
        #
        # 1. "afferma: ."  → "."  (colon left after quote stripped in sectional)
        final_text = re.sub(r':\s*\.', '.', final_text)
        # 2. "afferma che ." → "."  (dangling conjunction left after [CIT:id] stripped)
        final_text = re.sub(r'\s+(?:che|come|di)\s+\.', '.', final_text)
        # 3. "afferma ."  → "afferma."  (bare space before period from bare-quote removal)
        final_text = re.sub(r' \.', '.', final_text)
        # 4. "**nome** afferma."  → ""  (standalone attribution sentence with no content).
        #    After steps 1-3 all paths converge on this pattern: bold name + single bridge
        #    verb + period and nothing else. Safe to strip because a verb immediately
        #    followed by a period (no object) is never a meaningful sentence here.
        final_text = re.sub(r'\*\*[^*\n]+\*\*\s+\w+\.', '', final_text)

        # Check for unresolved [CIT:id] placeholders
        remaining_placeholders = re.findall(r'\[CIT:([^\]]+)\]', final_text)
        if remaining_placeholders:
            logger.error(f"UNRESOLVED CITATIONS: {remaining_placeholders}")
            # Replace with error marker
            for cit_id in remaining_placeholders:
                final_text = final_text.replace(
                    f"[CIT:{cit_id}]",
                    "[Citazione non risolta]"
                )
                registry.mark_resolved(cit_id, success=False, error="unresolved_placeholder")

        # Save text with resolved placeholders (link stripping deferred to chat.py)
        final_result["text"] = final_text

        # Extract unsupported claims (use existing method in surgeon)
        unsupported_claims = self.surgeon.extract_unsupported_claims(final_text)

        # Get final registry report
        integrity_report = registry.get_final_report()

        pipeline_metadata["citation_integrity"]["final"] = integrity_report
        pipeline_metadata["citation_integrity"]["unsupported_claims"] = unsupported_claims

        # === Finalize ===
        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        pipeline_metadata["end_time"] = end_time.isoformat()
        pipeline_metadata["duration_ms"] = duration_ms

        return {
            "text": final_result.get("text", ""),
            "citations": final_result.get("citations", []),
            "failed_citations": final_result.get("failed_citations", []),
            "extra_citation_ids": extra_citation_ids,
            "claims": claims,
            "sections": [
                {"party": s["party"], "has_evidence": s.get("has_evidence", False)}
                for s in sections
            ],
            "metadata": pipeline_metadata,
            "topic_statistics": topic_statistics,
            "citation_integrity": {
                "is_complete": integrity_report["is_complete"],
                "success_rate": integrity_report["success_rate"],
                "coherence_verified": coherence_report["all_coherent"],
                "unsupported_claims_count": len(unsupported_claims),
                "unresolved_placeholders": remaining_placeholders,
            }
        }

    def generate_sync(
        self,
        query: str,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Synchronous version of generate.
        """
        import asyncio
        return asyncio.run(self.generate(query, evidence_list))

    def _compute_topic_statistics(
        self,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute real statistics about the topic from retrieved evidence.

        Returns both aggregate counts (for the integrator prompt) and detailed
        lists (for the frontend clickable stats in the introduction).
        """
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

        from collections import Counter

        unique_speeches = set(
            e.get("speech_id") for e in evidence_list if e.get("speech_id")
        )
        unique_speakers = set(
            e.get("speaker_id") for e in evidence_list if e.get("speaker_id")
        )
        dates = [e.get("date") for e in evidence_list if e.get("date")]

        # Find the most frequent debate title to name the specific provvedimento
        debate_titles = [
            e.get("debate_title") for e in evidence_list
            if e.get("debate_title")
        ]
        most_common_title = (
            Counter(debate_titles).most_common(1)[0][0]
            if debate_titles else None
        )

        # Collect session numbers for academic traceability
        session_numbers = [
            e.get("session_number") for e in evidence_list
            if e.get("session_number")
        ]

        # --- Detailed lists for frontend clickable stats ---

        # Speakers: one entry per unique speaker with intervention count
        speaker_interventions: Dict[str, Dict[str, Any]] = {}
        for e in evidence_list:
            sid = e.get("speaker_id")
            if not sid:
                continue
            if sid not in speaker_interventions:
                speaker_interventions[sid] = {
                    "speaker_id": sid,
                    "speaker_name": e.get("speaker_name", ""),
                    "party": e.get("party", ""),
                    "coalition": e.get("coalition", ""),
                    "speech_ids": set(),
                }
            speech_id = e.get("speech_id")
            if speech_id:
                speaker_interventions[sid]["speech_ids"].add(speech_id)

        speakers_detail = []
        for info in speaker_interventions.values():
            speakers_detail.append({
                "speaker_id": info["speaker_id"],
                "speaker_name": info["speaker_name"],
                "party": info["party"],
                "coalition": info["coalition"],
                "intervention_count": len(info["speech_ids"]),
            })
        speakers_detail.sort(key=lambda x: x["intervention_count"], reverse=True)

        # Interventions: one entry per unique speech
        seen_speeches: Dict[str, Dict[str, Any]] = {}
        for e in evidence_list:
            speech_id = e.get("speech_id")
            if not speech_id or speech_id in seen_speeches:
                continue
            seen_speeches[speech_id] = {
                "speech_id": speech_id,
                "speaker_id": e.get("speaker_id", ""),
                "speaker_name": e.get("speaker_name", ""),
                "party": e.get("party", ""),
                "coalition": e.get("coalition", ""),
                "date": str(e.get("date", "")),
                "debate_title": e.get("debate_title", ""),
                "session_number": e.get("session_number", 0),
            }
        interventions_detail = sorted(
            seen_speeches.values(),
            key=lambda x: x["date"],
            reverse=True,
        )

        # Sessions: one entry per unique session number
        seen_sessions: Dict[int, Dict[str, Any]] = {}
        for e in evidence_list:
            sn = e.get("session_number")
            if not sn or sn in seen_sessions:
                continue
            seen_sessions[sn] = {
                "session_number": sn,
                "date": str(e.get("date", "")),
                "debate_title": e.get("debate_title", ""),
            }
        sessions_detail = sorted(
            seen_sessions.values(),
            key=lambda x: x["session_number"],
        )

        return {
            "intervention_count": len(unique_speeches),
            "speaker_count": len(unique_speakers),
            "first_date": min(dates) if dates else None,
            "last_date": max(dates) if dates else None,
            "debate_title": most_common_title,
            "session_numbers": list(set(session_numbers)),
            "speakers_detail": speakers_detail,
            "interventions_detail": interventions_detail,
            "sessions_detail": sessions_detail,
        }

    def _replace_party_paragraph(self, text: str, party: str, new_body: str) -> str:
        """
        Replace the body of a party's paragraph in the integrated text.

        Party paragraphs follow the integrator's mandatory format:
            "Per [Full Party Name], [body text]"
        and end before the next paragraph ("Per ") or section header ("##").

        Only the body is replaced; the "Per [Party], " prefix is preserved so
        the output keeps the correct paragraph structure.
        """
        party_escaped = re.escape(party)
        pattern = rf'(Per {party_escaped},\s+).*?(?=\n\nPer |\n\n##|\Z)'
        new_text, n = re.subn(pattern, rf'\g<1>{new_body}', text, flags=re.DOTALL)
        if n == 0:
            logger.warning(f"Could not locate paragraph for '{party}' in integrated text — skipping rewrite")
        else:
            logger.info(f"Rewrote citation-free paragraph for '{party}'")
        return new_text

    def _group_evidence_by_party(
        self,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group evidence by parliamentary party, sorted by authority score (descending).

        IMPORTANT: Excludes government members (GovernmentMember) as they have
        their own separate section.
        """
        all_parties = get_config().get_all_parties()
        by_party: Dict[str, List[Dict[str, Any]]] = {party: [] for party in all_parties}

        for evidence in evidence_list:
            # Skip government members - they go in the GOVERNO section
            if evidence.get("speaker_role") == "GovernmentMember":
                continue

            party = evidence.get("party", "Misto")

            # Handle potential party name variations
            if party not in by_party:
                # Try to find a matching party
                matched = False
                for known_party in all_parties:
                    if party in known_party or known_party in party:
                        by_party[known_party].append(evidence)
                        matched = True
                        break
                if not matched:
                    by_party["Misto"].append(evidence)
            else:
                by_party[party].append(evidence)

        # Sort each party's evidence by authority score (highest first)
        for party in by_party:
            by_party[party].sort(
                key=lambda e: e.get("authority_score", 0.0),
                reverse=True
            )

        return by_party

    def _check_coalition_balance(
        self,
        text: str
    ) -> Dict[str, Any]:
        """Check word count balance between majority and opposition sections.

        Based on Coverage-based Fairness (NAACL 2025) equal coverage principle.
        Logs a warning if the ratio exceeds 2:1.

        Returns:
            Dictionary with word counts, ratio, and balance_warning flag.
        """
        majority_section = ""
        opposition_section = ""

        # Extract sections by header
        sections = re.split(r'##\s+', text)
        for section in sections:
            if section.startswith("Posizioni della Maggioranza"):
                majority_section = section
            elif section.startswith("Posizioni dell'Opposizione") or section.startswith("Posizioni dell\u2019Opposizione"):
                opposition_section = section

        majority_words = len(majority_section.split())
        opposition_words = len(opposition_section.split())

        # Compute ratio (avoid division by zero)
        if opposition_words > 0:
            ratio = majority_words / opposition_words
        elif majority_words > 0:
            ratio = float('inf')
        else:
            ratio = 1.0

        return {
            "majority_words": majority_words,
            "opposition_words": opposition_words,
            "ratio": round(ratio, 2),
            "balance_warning": ratio > 2.0 or (1 / ratio if ratio > 0 else 0) > 2.0,
        }

    def _get_government_evidence(
        self,
        evidence_list: List[Dict[str, Any]],
        min_similarity: float = 0.35,
        max_per_speaker: int = 3,
    ) -> List[Dict[str, Any]]:
        """Get evidence from government members, sorted by relevance.

        Applies a minimum similarity threshold to exclude government members
        whose retrieved chunks are not topically relevant to the query.
        Graph-channel evidence defaults to 0.5, so only clearly irrelevant
        dense-channel chunks are filtered out.

        Additionally limits to max_per_speaker chunks per minister so that
        a single minister cannot dominate the government section.
        """
        gov = [
            e for e in evidence_list
            if e.get("speaker_role") == "GovernmentMember"
            and e.get("similarity", 0.5) >= min_similarity
        ]

        # Surface most relevant chunks first
        gov.sort(key=lambda e: e.get("similarity", 0.0), reverse=True)

        # Limit per speaker while preserving relevance order
        speaker_counts: dict = {}
        filtered = []
        for e in gov:
            sid = e.get("speaker_id", "")
            count = speaker_counts.get(sid, 0)
            if count < max_per_speaker:
                filtered.append(e)
                speaker_counts[sid] = count + 1

        return filtered
