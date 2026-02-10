"""
Survey models for A/B blind evaluation of ParliamentRAG vs Baseline RAG.

Users evaluate both responses (blind A/B) on the same dimensions,
rating each 1-5 and indicating preference per dimension.
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

    # Metadata
    evaluator_role: Optional[str] = Field(None, description="Role of evaluator")
    evaluation_context: Optional[str] = Field(None, description="Context of evaluation")


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

    evaluator_role: Optional[str] = None
    evaluation_context: Optional[str] = None


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
]


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
        "id": "overall_satisfaction",
        "category": "Valutazione Complessiva",
        "question": "Soddisfazione complessiva",
        "description": "Valutazione generale dell'esperienza con ciascuna risposta"
    }
]
