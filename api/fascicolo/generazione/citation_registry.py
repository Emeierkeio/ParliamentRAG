"""Registro delle citazioni lungo tutta la pipeline.

Tiene il legame tra le evidenze recuperate, i segnaposto di citazione nel
testo generato e le citazioni finali formattate dal chirurgo.
"""
import re
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CitationStatus(Enum):
    """Stato di una citazione lungo la pipeline."""
    REGISTERED = "registered"       # evidenza disponibile
    BOUND = "bound"                 # assegnata a una sezione del testo
    IN_TEXT = "in_text"            # segnaposto trovato nel testo
    RESOLVED = "resolved"          # formattata
    FAILED = "failed"              # non risolta
    ORPHANED = "orphaned"          # segnaposto presente ma senza risoluzione


@dataclass
class CitationBinding:
    """Legame tra evidenza, testo e citazione."""
    evidence_id: str
    status: CitationStatus = CitationStatus.REGISTERED

    speaker_name: Optional[str] = None
    party: Optional[str] = None
    quote_preview: Optional[str] = None

    section_party: Optional[str] = None
    intro_text: Optional[str] = None

    placeholder_count: int = 0     # quanti [CIT:id] trovati
    resolved_count: int = 0        # quanti risolti

    semantic_coherence_score: Optional[float] = None
    error_message: Optional[str] = None


class CitationRegistry:
    """Segue le citazioni lungo la pipeline.

    Ciclo: register_evidence all'inizio, bind_citation durante la scrittura
    delle sezioni, verify_placeholders_in_text dopo l'integrazione,
    mark_resolved nel chirurgo, infine get_final_report.
    """

    def __init__(self):
        self._bindings: Dict[str, CitationBinding] = {}
        self._expected_citations: Set[str] = set()
        self._pipeline_stage: str = "init"

    def register_evidence(self, evidence_list: List[Dict[str, Any]]) -> None:
        """Registra all'inizio della pipeline tutte le evidenze disponibili."""
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
        """Lega una citazione alla sezione di un partito."""
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
        """Controlla che tutti i segnaposto [CIT:id] attesi siano sopravvissuti all'integrazione.

        Restituisce un resoconto con gli ID mancanti e quelli inattesi.
        """
        self._pipeline_stage = "placeholder_verification"

        found_ids = set(re.findall(r'\[CIT:([^\]]+)\]', text))
        missing = self._expected_citations - found_ids
        unexpected = found_ids - self._expected_citations

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
        """Segna una citazione come risolta o fallita."""
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
        """Imposta il punteggio di coerenza semantica (0-1) di una citazione."""
        if evidence_id in self._bindings:
            self._bindings[evidence_id].semantic_coherence_score = score

    def get_expected_citations(self) -> Set[str]:
        """L'insieme degli ID di citazione attesi."""
        return self._expected_citations.copy()

    def get_final_report(self) -> Dict[str, Any]:
        """Resoconto finale sull'integrità delle citazioni.

        Contiene i conteggi di risolte, fallite e orfane, il tasso di
        successo e i legami divisi per stato.
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

    def reset(self) -> None:
        """Svuota il registro per un nuovo giro della pipeline."""
        self._bindings.clear()
        self._expected_citations.clear()
        self._pipeline_stage = "init"
