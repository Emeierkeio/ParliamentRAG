"""4-stage generation pipeline for multi-view RAG with citation integrity."""
from .pipeline import GenerationPipeline
from .analyst import ClaimAnalyst
from .sectional import SectionalWriter
from .integrator import NarrativeIntegrator
from .surgeon import CitationSurgeon
from .citation_registry import CitationRegistry, CitationStatus, CitationBinding
from .coherence_validator import CoherenceValidator
from .evidence_first_writer import EvidenceFirstWriter

__all__ = [
    # Core pipeline
    "GenerationPipeline",
    "ClaimAnalyst",
    "SectionalWriter",
    "NarrativeIntegrator",
    "CitationSurgeon",
    # Citation integrity
    "CitationRegistry",
    "CitationStatus",
    "CitationBinding",
    "CoherenceValidator",
    "EvidenceFirstWriter",
]
