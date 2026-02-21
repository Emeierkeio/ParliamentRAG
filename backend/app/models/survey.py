"""
Survey models for A/B blind evaluation of ParliamentRAG vs Baseline RAG,
and simple Likert-scale evaluation for queries without a predefined baseline.

A/B evaluation: users rate both responses (blind) and indicate preference.
Simple evaluation: users rate only the system response on 4 Likert dimensions.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import uuid4
from enum import Enum


class RatingScale(int, Enum):
    """1-5 star rating scale"""
    VERY_POOR = 1
    POOR = 2
    AVERAGE = 3
    GOOD = 4
    EXCELLENT = 5


# Valid issue tags for individual citation evaluation
CITATION_ISSUES = [
    "out_of_context",
    "truncated",
    "wrong_attribution",
    "duplicate",
    "unverifiable",
    "none",
]


class CitationEvaluation(BaseModel):
    """Evaluation of a single citation within a response."""
    evidence_id: str = Field(..., description="chunk_id of the citation")
    relevance: int = Field(..., ge=1, le=5, description="How relevant is this citation to the query/response")
    faithfulness: int = Field(..., ge=1, le=5, description="How faithfully does the quote represent the original speech")
    informativeness: int = Field(..., ge=1, le=5, description="How much value does this citation add")
    attribution: Literal["correct", "incorrect", "unverifiable"] = Field(
        ..., description="Is the speaker/group/date attribution correct"
    )
    issues: List[str] = Field(default_factory=list, description="Issue tags for quick triage")


class ABRating(BaseModel):
    """Rating for a single dimension, comparing Response A and Response B."""
    rating_a: int = Field(..., ge=1, le=5, description="Rating for Risposta A")
    rating_b: int = Field(..., ge=1, le=5, description="Rating for Risposta B")
    preference: Literal["A", "B", "equal"] = Field(..., description="Which response is better")


class SurveyResponse(BaseModel):
    """Complete A/B survey response for a single chat session."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    chat_id: str = Field(..., description="Associated chat history ID")
    timestamp: datetime = Field(default_factory=datetime.now)

    # A/B comparative ratings per dimension
    answer_quality: ABRating
    answer_clarity: ABRating
    answer_completeness: ABRating
    citations_relevance: ABRating
    citations_accuracy: ABRating
    balance_perception: ABRating
    balance_fairness: ABRating

    # Overall
    overall_satisfaction_a: int = Field(..., ge=1, le=5, description="Overall satisfaction for Risposta A")
    overall_satisfaction_b: int = Field(..., ge=1, le=5, description="Overall satisfaction for Risposta B")
    overall_preference: Literal["A", "B", "equal"] = Field(..., description="Overall preferred response")

    would_recommend: bool = Field(..., description="Would recommend to colleagues")

    # Qualitative feedback
    feedback_positive: Optional[str] = Field(None, max_length=1000, description="What worked well")
    feedback_improvement: Optional[str] = Field(None, max_length=1000, description="Suggestions for improvement")

    # Individual citation evaluations
    citation_evaluations_a: List[CitationEvaluation] = Field(default_factory=list, description="Per-citation evaluations for Response A")
    citation_evaluations_b: List[CitationEvaluation] = Field(default_factory=list, description="Per-citation evaluations for Response B")

    # Source authority evaluation — optional (added after initial schema; None for legacy records)
    source_relevance: Optional[ABRating] = Field(None, description="Rilevanza tematica degli esperti citati")
    source_authority: Optional[ABRating] = Field(None, description="Autorevolezza istituzionale degli esperti")
    source_coverage: Optional[ABRating] = Field(None, description="Copertura delle coalizioni")

    # Metadata
    evaluator_role: Optional[str] = Field(None, description="Role of evaluator")
    evaluation_context: Optional[str] = Field(None, description="Context of evaluation")
    evaluator_id: Optional[str] = Field(None, description="Unique identifier for the evaluator")
    ab_assignment: Optional[Dict[str, str]] = Field(None, description="Per-evaluator A/B assignment, e.g. {'A': 'system', 'B': 'baseline'}")


class SurveyResponseCreate(BaseModel):
    """Model for creating a new A/B survey response."""
    chat_id: str

    # A/B comparative ratings per dimension
    answer_quality: ABRating
    answer_clarity: ABRating
    answer_completeness: ABRating
    citations_relevance: ABRating
    citations_accuracy: ABRating
    balance_perception: ABRating
    balance_fairness: ABRating

    # Overall
    overall_satisfaction_a: int = Field(..., ge=1, le=5)
    overall_satisfaction_b: int = Field(..., ge=1, le=5)
    overall_preference: Literal["A", "B", "equal"]

    would_recommend: bool

    feedback_positive: Optional[str] = None
    feedback_improvement: Optional[str] = None

    # Individual citation evaluations
    citation_evaluations_a: List[CitationEvaluation] = Field(default_factory=list)
    citation_evaluations_b: List[CitationEvaluation] = Field(default_factory=list)

    # Source authority evaluation (optional)
    source_relevance: Optional[ABRating] = None
    source_authority: Optional[ABRating] = None
    source_coverage: Optional[ABRating] = None

    evaluator_role: Optional[str] = None
    evaluation_context: Optional[str] = None

    # Evaluator identifier (for multi-evaluator study)
    evaluator_id: Optional[str] = Field(None, description="Unique identifier for the evaluator (e.g. from ?evaluator= URL param)")

    # A/B assignment (provided by frontend when using evaluation_set baseline)
    ab_assignment: Optional[Dict[str, str]] = Field(
        None, description="e.g. {'A': 'system', 'B': 'baseline'} — set if using evaluation_set baseline"
    )
    evaluation_set_topic: Optional[str] = Field(
        None, description="Topic name from evaluation_set.json if this is an evaluation_set A/B"
    )


# ── Simple Likert Evaluation (for queries without a predefined baseline) ──────

# Dimensions for simple Likert evaluation
SIMPLE_DIMENSIONS = [
    "answer_clarity",
    "answer_quality",
    "balance_perception",
    "balance_fairness",
]

SIMPLE_DIMENSION_LABELS = {
    "answer_clarity": "Chiarezza espositiva",
    "answer_quality": "Qualità complessiva percepita",
    "balance_perception": "Bilanciamento percepito",
    "balance_fairness": "Equità rappresentazione",
}


class SimpleRatingResponse(BaseModel):
    """Simple Likert-scale evaluation of a single chat response (no baseline needed)."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    chat_id: str = Field(..., description="Associated chat history ID")
    timestamp: datetime = Field(default_factory=datetime.now)

    answer_clarity: int = Field(..., ge=1, le=5, description="Chiarezza espositiva (1-5)")
    answer_quality: int = Field(..., ge=1, le=5, description="Qualità complessiva percepita (1-5)")
    balance_perception: int = Field(..., ge=1, le=5, description="Bilanciamento percepito (1-5)")
    balance_fairness: int = Field(..., ge=1, le=5, description="Equità rappresentazione (1-5)")

    feedback: Optional[str] = Field(None, max_length=1000, description="Commento libero opzionale")
    evaluator_id: Optional[str] = Field(None, description="Unique identifier for the evaluator")


class SimpleRatingCreate(BaseModel):
    """Model for creating a new simple Likert rating."""
    chat_id: str
    answer_clarity: int = Field(..., ge=1, le=5)
    answer_quality: int = Field(..., ge=1, le=5)
    balance_perception: int = Field(..., ge=1, le=5)
    balance_fairness: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = None
    evaluator_id: Optional[str] = Field(None, description="Unique identifier for the evaluator")


class SurveyWithChat(BaseModel):
    """Survey response with associated chat metadata."""
    survey: SurveyResponse
    chat_query: str
    chat_preview: str
    chat_timestamp: datetime


# Dimensions used for A/B comparison
AB_DIMENSIONS = [
    "answer_quality",
    "answer_clarity",
    "answer_completeness",
    "citations_relevance",
    "citations_accuracy",
    "balance_perception",
    "balance_fairness",
    "source_relevance",
    "source_authority",
    "source_coverage",
]

# Optional dims added after the initial schema (may be absent in legacy Neo4j records)
OPTIONAL_AB_DIMS = {"source_relevance", "source_authority", "source_coverage"}


class SurveyStats(BaseModel):
    """Aggregated A/B survey statistics (de-blinded)."""
    total_surveys: int

    # De-blinded averages per dimension
    system_avg_per_dimension: Dict[str, float]
    baseline_avg_per_dimension: Dict[str, float]

    # Overall satisfaction averages
    system_avg_overall: float
    baseline_avg_overall: float

    # Win rates (de-blinded)
    system_win_rate: float   # % of preferences favoring system
    baseline_win_rate: float  # % of preferences favoring baseline
    tie_rate: float           # % equal

    # Per-dimension preference counts (de-blinded)
    per_dimension_preference: Dict[str, Dict[str, int]]  # dim -> {"system": N, "baseline": N, "equal": N}

    recommendation_rate: float


class SurveyListResponse(BaseModel):
    """Response for listing surveys."""
    surveys: List[SurveyWithChat]
    total: int
    stats: Optional[SurveyStats] = None


# Survey questions configuration (for frontend) - A/B format
SURVEY_QUESTIONS = [
    {
        "id": "answer_quality",
        "category": "Qualita Risposta",
        "question": "Qualita complessiva della risposta",
        "description": "Considera l'utilita pratica per il lavoro giornalistico"
    },
    {
        "id": "answer_clarity",
        "category": "Qualita Risposta",
        "question": "Chiarezza e leggibilita della risposta",
        "description": "Valuta la struttura, il linguaggio e la facilita di comprensione"
    },
    {
        "id": "answer_completeness",
        "category": "Qualita Risposta",
        "question": "Completezza delle informazioni",
        "description": "Considera se mancano informazioni importanti"
    },
    {
        "id": "citations_relevance",
        "category": "Citazioni",
        "question": "Pertinenza delle citazioni parlamentari",
        "description": "Valuta se le citazioni supportano effettivamente la risposta"
    },
    {
        "id": "citations_accuracy",
        "category": "Citazioni",
        "question": "Accuratezza delle attribuzioni",
        "description": "Considera se deputato, data e contesto sono corretti"
    },
    {
        "id": "balance_perception",
        "category": "Bilanciamento Politico",
        "question": "Bilanciamento politico percepito",
        "description": "Valuta se sono rappresentate diverse posizioni politiche"
    },
    {
        "id": "balance_fairness",
        "category": "Bilanciamento Politico",
        "question": "Equita nella rappresentazione",
        "description": "Considera se c'e imparzialita nella presentazione"
    },
    {
        "id": "source_relevance",
        "category": "Autorità Esperti",
        "question": "Rilevanza tematica degli esperti",
        "description": "Gli esperti citati sono le voci parlamentari più attive e pertinenti su questo tema?"
    },
    {
        "id": "source_authority",
        "category": "Autorità Esperti",
        "question": "Autorevolezza istituzionale",
        "description": "Le figure citate ricoprono ruoli istituzionali rilevanti (commissioni, presidenze, portavoce)?"
    },
    {
        "id": "source_coverage",
        "category": "Autorità Esperti",
        "question": "Copertura delle coalizioni",
        "description": "Le principali forze politiche sono rappresentate in modo equilibrato?"
    },
    {
        "id": "overall_satisfaction",
        "category": "Valutazione Complessiva",
        "question": "Soddisfazione complessiva",
        "description": "Valutazione generale dell'esperienza con ciascuna risposta"
    }
]
