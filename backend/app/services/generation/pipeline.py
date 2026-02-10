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
        self.analyst = ClaimAnalyst()
        self.sectional_writer = SectionalWriter()
        self.integrator = NarrativeIntegrator()
        self.surgeon = CitationSurgeon()
        self.coherence_validator = CoherenceValidator()

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

        # Use integrate_with_guard to verify citation preservation
        integrated = self.integrator.integrate_with_guard(query, sections, registry)

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
