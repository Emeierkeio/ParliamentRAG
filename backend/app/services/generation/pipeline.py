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
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime

from .analyst import ClaimAnalyst
from .sectional import SectionalWriter, ALL_PARTIES
from .integrator import NarrativeIntegrator
from .surgeon import CitationSurgeon
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

        self.analyst = ClaimAnalyst()
        self.sectional_writer = SectionalWriter()
        self.integrator = NarrativeIntegrator()
        self.surgeon = CitationSurgeon()
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

        if not coherence_report["all_coherent"]:
            incoherent = self.coherence_validator.get_incoherent_citations(coherence_report)
            logger.warning(f"Coherence issues: {len(incoherent)} incoherent citations")
            for ic in incoherent[:3]:  # Log first 3
                logger.warning(f"  - {ic.get('evidence_id')}: {ic.get('warning')}")

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
            text=integrated.get("text", ""),
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
                # Extract quote from display text (strip guillemets if present)
                quote = display_text.strip()
                if quote.startswith("«") and quote.endswith("»"):
                    quote = quote[1:-1]
                # Strip speaker/party/date suffix after em-dash if present
                if " — " in quote:
                    quote = quote.split(" — ")[0].strip()

                final_result.get("citations", []).append({
                    "evidence_id": eid,
                    "quote_text": quote,
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
                    f"(quote: '{quote[:60]}...')"
                )

        if len(tracked_ids) > final_result.get("total_citations", 0):
            recovered = len(tracked_ids) - final_result.get("total_citations", 0)
            logger.info(f"Recovered {recovered} untracked citations from final text")

        # Check for bare «» citations not wrapped in markdown links
        bare_citations = re.findall(r'(?<!\[)«[^»]+»(?!\])', final_text)
        if bare_citations:
            logger.warning(
                f"Found {len(bare_citations)} bare citations without markdown links: "
                f"{[c[:50] for c in bare_citations[:3]]}"
            )

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

    async def generate_baseline(
        self,
        query: str,
        evidence_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate a baseline RAG response WITHOUT authority scoring
        and WITHOUT citation correction (surgeon/coherence).

        Uses the same evidence but with uniform authority scores (0.5)
        and skips Stage 4 (Citation Surgeon) and coherence validation.

        Sections are written sequentially (not in parallel) to avoid
        OpenAI rate limit bursts after the main pipeline.
        """
        start_time = datetime.now()
        logger.info(f"[BASELINE-PIPELINE] === Starting generate_baseline ===")
        logger.info(f"[BASELINE-PIPELINE] Query: '{query[:100]}...'")
        logger.info(f"[BASELINE-PIPELINE] Evidence count: {len(evidence_list)}")

        # 1. Neutralize authority scores
        baseline_evidence = [
            {**e, "authority_score": 0.5} for e in evidence_list
        ]
        logger.info(f"[BASELINE-PIPELINE] Step 1: Neutralized {len(baseline_evidence)} evidence items to authority_score=0.5")

        # 2. Stage 1: Analyst (async to avoid blocking the event loop)
        logger.info("[BASELINE-PIPELINE] Step 2: Running analyst.analyze_async...")
        try:
            claims_result = await self.analyst.analyze_async(query, baseline_evidence)
            claims = claims_result.get("claims", [])
            logger.info(f"[BASELINE-PIPELINE] Step 2 done: {len(claims)} claims extracted")
        except Exception as e:
            logger.error(f"[BASELINE-PIPELINE] Step 2 FAILED: {type(e).__name__}: {e}", exc_info=True)
            raise

        # 3. Stage 2: Sectional Writer — SEQUENTIAL to avoid RPM burst
        # The main pipeline already consumed ~13 API calls; running 11
        # more in parallel here would exceed the 60 RPM rate limit.
        evidence_by_party = self._group_evidence_by_party(baseline_evidence)
        government_evidence = self._get_government_evidence(baseline_evidence)

        sections = []
        all_parties = list(evidence_by_party.keys())
        logger.info(f"[BASELINE-PIPELINE] Step 3: Writing sections for {len(all_parties)} parties, gov_evidence={'yes' if government_evidence else 'no'}")

        # Government section first (if evidence exists)
        if government_evidence:
            logger.info(f"[BASELINE-PIPELINE] Step 3: Writing GOVERNO section ({len(government_evidence)} evidence)...")
            try:
                section = await self.sectional_writer._write_section(
                    query=query,
                    party="GOVERNO",
                    evidence=government_evidence,
                    claims=claims,
                    is_government=True
                )
                sections.append(section)
                logger.info(f"[BASELINE-PIPELINE] Step 3: GOVERNO section done: {len(section.get('text', ''))} chars")
            except Exception as e:
                logger.error(f"[BASELINE-PIPELINE] Step 3: GOVERNO section FAILED: {type(e).__name__}: {e}", exc_info=True)
                raise

        # Party sections sequentially
        for i, party in enumerate(all_parties):
            evidence = evidence_by_party.get(party, [])
            logger.info(f"[BASELINE-PIPELINE] Step 3: Writing party {i+1}/{len(all_parties)}: '{party}' ({len(evidence)} evidence)...")
            try:
                section = await self.sectional_writer._write_section(
                    query=query,
                    party=party,
                    evidence=evidence,
                    claims=claims,
                    is_government=False
                )
                sections.append(section)
                logger.info(f"[BASELINE-PIPELINE] Step 3: '{party}' section done: {len(section.get('text', ''))} chars")
            except Exception as e:
                logger.error(f"[BASELINE-PIPELINE] Step 3: '{party}' section FAILED: {type(e).__name__}: {e}", exc_info=True)
                raise

        logger.info(f"[BASELINE-PIPELINE] Step 3 complete: {len(sections)} total sections")

        # 4. Stage 3: Integrator WITHOUT guard (simple integrate)
        # Pass topic_statistics for a fair A/B comparison
        logger.info("[BASELINE-PIPELINE] Step 4: Running integrator.integrate...")
        topic_statistics = self._compute_topic_statistics(baseline_evidence)
        try:
            integrated = self.integrator.integrate(
                query, sections, topic_statistics=topic_statistics
            )
            logger.info(f"[BASELINE-PIPELINE] Step 4 done: integrated keys={list(integrated.keys())}, text_len={len(integrated.get('text', ''))}")
        except Exception as e:
            logger.error(f"[BASELINE-PIPELINE] Step 4 FAILED: {type(e).__name__}: {e}", exc_info=True)
            raise

        # 5. Remove unresolved [CIT:id] placeholders and clean up artifacts
        text = integrated.get("text", "")
        logger.info(f"[BASELINE-PIPELINE] Step 5: Cleaning text (pre-clean len={len(text)})")
        # Remove placeholders, including any space before punctuation
        text = re.sub(r'\s*\[CIT:[^\]]+\]', '', text)
        # Clean up double spaces
        text = re.sub(r'  +', ' ', text)
        # Clean up space before punctuation left by removals
        text = re.sub(r'\s+([.,:;!?)])', r'\1', text)
        # Clean up empty lines
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        logger.info(f"[BASELINE-PIPELINE] Step 5: Cleaned text (post-clean len={len(text)})")

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"Baseline generation complete: {len(text)} chars, "
            f"{len(sections)} sections, {duration_ms:.1f}ms"
        )

        return {
            "text": text,
            "citations": [],
            "sections": [
                {"party": s["party"], "has_evidence": s.get("has_evidence", False)}
                for s in sections
            ],
            "metadata": {
                "pipeline": "baseline",
                "duration_ms": duration_ms,
                "claims_count": len(claims),
                "sections_count": len(sections),
            }
        }

    def _compute_topic_statistics(
        self,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute real statistics about the topic from retrieved evidence."""
        if not evidence_list:
            return {
                "intervention_count": 0,
                "speaker_count": 0,
                "first_date": None,
                "last_date": None,
                "debate_title": None,
            }

        unique_speeches = set(
            e.get("speech_id") for e in evidence_list if e.get("speech_id")
        )
        unique_speakers = set(
            e.get("speaker_id") for e in evidence_list if e.get("speaker_id")
        )
        dates = [e.get("date") for e in evidence_list if e.get("date")]

        # Find the most frequent debate title to name the specific provvedimento
        from collections import Counter
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

        return {
            "intervention_count": len(unique_speeches),
            "speaker_count": len(unique_speakers),
            "first_date": min(dates) if dates else None,
            "last_date": max(dates) if dates else None,
            "debate_title": most_common_title,
            "session_numbers": list(set(session_numbers)),
        }

    def _group_evidence_by_party(
        self,
        evidence_list: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group evidence by parliamentary party, sorted by authority score (descending).

        IMPORTANT: Excludes government members (GovernmentMember) as they have
        their own separate section.
        """
        by_party: Dict[str, List[Dict[str, Any]]] = {party: [] for party in ALL_PARTIES}

        for evidence in evidence_list:
            # Skip government members - they go in the GOVERNO section
            if evidence.get("speaker_role") == "GovernmentMember":
                continue

            party = evidence.get("party", "Misto")

            # Handle potential party name variations
            if party not in by_party:
                # Try to find a matching party
                matched = False
                for known_party in ALL_PARTIES:
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

    def _get_government_evidence(
        self,
        evidence_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get evidence from government members."""
        return [
            e for e in evidence_list
            if e.get("speaker_role") == "GovernmentMember"
        ]
