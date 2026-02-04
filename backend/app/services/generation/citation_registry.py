"""
Citation Registry for pipeline-wide citation tracking.

Maintains binding between:
- Claims (from analyst)
- Evidence (from retrieval)
- Citation placeholders (in generated text)
- Final formatted citations (from surgeon)

This module provides complete traceability and verification
of citations throughout the generation pipeline.
"""
import re
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CitationStatus(Enum):
    """Status of a citation through the pipeline."""
    REGISTERED = "registered"       # Evidence available
    BOUND = "bound"                 # Assigned to text section
    IN_TEXT = "in_text"            # Placeholder found in text
    RESOLVED = "resolved"          # Successfully formatted
    FAILED = "failed"              # Could not be resolved
    ORPHANED = "orphaned"          # Placeholder present but no resolution


@dataclass
class CitationBinding:
    """Binding between evidence, text, and citation."""
    evidence_id: str
    status: CitationStatus = CitationStatus.REGISTERED

    # Evidence metadata
    speaker_name: Optional[str] = None
    party: Optional[str] = None
    quote_preview: Optional[str] = None

    # Text binding
    section_party: Optional[str] = None
    intro_text: Optional[str] = None

    # Resolution tracking
    placeholder_count: int = 0     # How many [CIT:id] found
    resolved_count: int = 0        # How many successfully resolved

    # Verification
    semantic_coherence_score: Optional[float] = None
    error_message: Optional[str] = None


class CitationRegistry:
    """
    Central registry for tracking citations through the pipeline.

    Usage:
    1. Register all available evidence at start
    2. Mark citations as bound when written into sections
    3. Verify all placeholders present after integration
    4. Track resolution status in surgeon stage
    5. Final verification: all citations resolved

    Example:
        registry = CitationRegistry()
        registry.register_evidence(evidence_list)

        # During sectional writing
        registry.bind_citation("e1", "PARTY", "Intro text...")

        # After integration
        report = registry.verify_placeholders_in_text(integrated_text)

        # After surgeon
        registry.mark_resolved("e1", success=True)

        # Final report
        final = registry.get_final_report()
    """

    def __init__(self):
        self._bindings: Dict[str, CitationBinding] = {}
        self._expected_citations: Set[str] = set()
        self._pipeline_stage: str = "init"

    def register_evidence(self, evidence_list: List[Dict[str, Any]]) -> None:
        """
        Register all available evidence at pipeline start.

        Args:
            evidence_list: List of evidence dictionaries with evidence_id
        """
        self._pipeline_stage = "registration"

        for e in evidence_list:
            evidence_id = e.get("evidence_id", "")
            if not evidence_id:
                continue

            self._bindings[evidence_id] = CitationBinding(
                evidence_id=evidence_id,
                status=CitationStatus.REGISTERED,
                speaker_name=e.get("speaker_name"),
                party=e.get("party"),
                quote_preview=(e.get("quote_text") or e.get("chunk_text", ""))[:100]
            )

        logger.info(f"CitationRegistry: Registered {len(self._bindings)} evidence pieces")

    def bind_citation(
        self,
        evidence_id: str,
        section_party: str,
        intro_text: str
    ) -> bool:
        """
        Mark a citation as bound to a text section.

        Args:
            evidence_id: The evidence ID being cited
            section_party: The party section where this citation appears
            intro_text: The introductory text leading to the citation

        Returns:
            True if binding was successful
        """
        if evidence_id not in self._bindings:
            logger.warning(f"Binding unknown evidence: {evidence_id}")
            self._bindings[evidence_id] = CitationBinding(
                evidence_id=evidence_id,
                status=CitationStatus.BOUND
            )

        binding = self._bindings[evidence_id]
        binding.status = CitationStatus.BOUND
        binding.section_party = section_party
        binding.intro_text = intro_text

        self._expected_citations.add(evidence_id)
        logger.debug(f"Bound citation {evidence_id} to section {section_party}")
        return True

    def verify_placeholders_in_text(self, text: str) -> Dict[str, Any]:
        """
        Verify all expected citations have placeholders in text.

        Called after integrator stage to ensure no citations were lost.

        Args:
            text: The integrated text with [CIT:id] placeholders

        Returns:
            Verification report with missing/unexpected citations
        """
        self._pipeline_stage = "placeholder_verification"

        # Find all [CIT:id] in text
        found_ids = set(re.findall(r'\[CIT:([^\]]+)\]', text))

        # Check expected vs found
        missing = self._expected_citations - found_ids
        unexpected = found_ids - self._expected_citations

        # Update binding statuses
        for eid in found_ids:
            if eid in self._bindings:
                self._bindings[eid].status = CitationStatus.IN_TEXT
                self._bindings[eid].placeholder_count = text.count(f"[CIT:{eid}]")

        for eid in missing:
            if eid in self._bindings:
                self._bindings[eid].status = CitationStatus.ORPHANED
                self._bindings[eid].error_message = "Placeholder missing after integration"

        if missing:
            logger.warning(f"CitationRegistry: {len(missing)} citations missing after integration: {list(missing)[:5]}")

        if unexpected:
            logger.info(f"CitationRegistry: {len(unexpected)} unexpected citations found: {list(unexpected)[:5]}")

        return {
            "expected": len(self._expected_citations),
            "found": len(found_ids),
            "missing": list(missing),
            "unexpected": list(unexpected),
            "all_present": len(missing) == 0
        }

    def mark_resolved(
        self,
        evidence_id: str,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Mark a citation as resolved or failed.

        Args:
            evidence_id: The evidence ID that was processed
            success: Whether resolution was successful
            error: Optional error message if failed
        """
        if evidence_id in self._bindings:
            binding = self._bindings[evidence_id]
            binding.status = CitationStatus.RESOLVED if success else CitationStatus.FAILED
            binding.resolved_count += 1 if success else 0
            if error:
                binding.error_message = error
            logger.debug(f"Citation {evidence_id} marked as {'resolved' if success else 'failed'}")

    def set_coherence_score(
        self,
        evidence_id: str,
        score: float
    ) -> None:
        """
        Set the semantic coherence score for a citation.

        Args:
            evidence_id: The evidence ID
            score: Coherence score between 0 and 1
        """
        if evidence_id in self._bindings:
            self._bindings[evidence_id].semantic_coherence_score = score

    def get_expected_citations(self) -> Set[str]:
        """Get the set of expected citation IDs."""
        return self._expected_citations.copy()

    def get_binding(self, evidence_id: str) -> Optional[CitationBinding]:
        """Get a specific binding by evidence ID."""
        return self._bindings.get(evidence_id)

    def get_final_report(self) -> Dict[str, Any]:
        """
        Generate final citation integrity report.

        Returns:
            Comprehensive report including:
            - Total registered evidence
            - Expected citations count
            - Resolved/failed/orphaned counts
            - Success rate
            - Detailed breakdown by status
        """
        total = len(self._bindings)
        by_status: Dict[str, List[Dict[str, Any]]] = {}

        for binding in self._bindings.values():
            status_name = binding.status.value
            if status_name not in by_status:
                by_status[status_name] = []
            by_status[status_name].append({
                "evidence_id": binding.evidence_id,
                "speaker": binding.speaker_name,
                "party": binding.party,
                "section_party": binding.section_party,
                "coherence_score": binding.semantic_coherence_score,
                "error": binding.error_message
            })

        resolved = len(by_status.get("resolved", []))
        failed = len(by_status.get("failed", []))
        orphaned = len(by_status.get("orphaned", []))
        expected_count = len(self._expected_citations)

        success_rate = resolved / expected_count if expected_count > 0 else 1.0

        return {
            "total_registered": total,
            "total_expected": expected_count,
            "resolved": resolved,
            "failed": failed,
            "orphaned": orphaned,
            "success_rate": success_rate,
            "is_complete": (failed == 0 and orphaned == 0 and resolved == expected_count),
            "by_status": by_status,
            "pipeline_stage": self._pipeline_stage
        }

    def get_bindings(self) -> Dict[str, CitationBinding]:
        """Get all bindings for debugging."""
        return self._bindings.copy()

    def get_failed_citations(self) -> List[Dict[str, Any]]:
        """Get list of failed citations with details."""
        failed = []
        for binding in self._bindings.values():
            if binding.status in (CitationStatus.FAILED, CitationStatus.ORPHANED):
                failed.append({
                    "evidence_id": binding.evidence_id,
                    "status": binding.status.value,
                    "speaker": binding.speaker_name,
                    "party": binding.party,
                    "error": binding.error_message
                })
        return failed

    def reset(self) -> None:
        """Reset the registry for a new pipeline run."""
        self._bindings.clear()
        self._expected_citations.clear()
        self._pipeline_stage = "init"
