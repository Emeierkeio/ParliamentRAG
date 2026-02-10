"""
Survey models for user evaluation of ParliamentRAG responses.
Designed for professional journalists to evaluate system quality.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
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


class SurveyQuestion(BaseModel):
    """Individual survey question response"""
    question_id: str
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5 stars")


class SurveyResponse(BaseModel):
    """Complete survey response for a single chat session"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    chat_id: str = Field(..., description="Associated chat history ID")
    timestamp: datetime = Field(default_factory=datetime.now)

    # Core evaluation metrics (1-5 scale)
    answer_quality: int = Field(..., ge=1, le=5, description="Overall answer quality")
    answer_clarity: int = Field(..., ge=1, le=5, description="Clarity and readability")
    answer_completeness: int = Field(..., ge=1, le=5, description="Completeness of information")

    # Citations evaluation
    citations_relevance: int = Field(..., ge=1, le=5, description="Relevance of parliamentary citations")
    citations_accuracy: int = Field(..., ge=1, le=5, description="Accuracy of citation attribution")

    # Political balance evaluation
    balance_perception: int = Field(..., ge=1, le=5, description="Perceived political balance")
    balance_fairness: int = Field(..., ge=1, le=5, description="Fair representation of viewpoints")

    # Feature-specific evaluations
    compass_usefulness: int = Field(..., ge=1, le=5, description="Usefulness of ideological compass")
    experts_usefulness: int = Field(..., ge=1, le=5, description="Usefulness of expert identification")

    # Baseline comparison (ParliamentRAG vs naive RAG)
    baseline_improvement: int = Field(..., ge=1, le=5, description="Perceived improvement over standard RAG")
    authority_value: int = Field(..., ge=1, le=5, description="Value of authority scoring feature")
    citation_pipeline_value: int = Field(..., ge=1, le=5, description="Value of citation verification pipeline")

    # Overall satisfaction
    overall_satisfaction: int = Field(..., ge=1, le=5, description="Overall satisfaction")
    would_recommend: bool = Field(..., description="Would recommend to colleagues")

    # Qualitative feedback
    feedback_positive: Optional[str] = Field(None, max_length=1000, description="What worked well")
    feedback_improvement: Optional[str] = Field(None, max_length=1000, description="Suggestions for improvement")

    # Metadata
    evaluator_role: Optional[str] = Field(None, description="Role of evaluator (e.g., journalist, researcher)")
    evaluation_context: Optional[str] = Field(None, description="Context of evaluation (e.g., article research)")


class SurveyResponseCreate(BaseModel):
    """Model for creating a new survey response"""
    chat_id: str

    answer_quality: int = Field(..., ge=1, le=5)
    answer_clarity: int = Field(..., ge=1, le=5)
    answer_completeness: int = Field(..., ge=1, le=5)

    citations_relevance: int = Field(..., ge=1, le=5)
    citations_accuracy: int = Field(..., ge=1, le=5)

    balance_perception: int = Field(..., ge=1, le=5)
    balance_fairness: int = Field(..., ge=1, le=5)

    compass_usefulness: int = Field(..., ge=1, le=5)
    experts_usefulness: int = Field(..., ge=1, le=5)

    baseline_improvement: int = Field(..., ge=1, le=5)
    authority_value: int = Field(..., ge=1, le=5)
    citation_pipeline_value: int = Field(..., ge=1, le=5)

    overall_satisfaction: int = Field(..., ge=1, le=5)
    would_recommend: bool

    feedback_positive: Optional[str] = None
    feedback_improvement: Optional[str] = None

    evaluator_role: Optional[str] = None
    evaluation_context: Optional[str] = None


class SurveyWithChat(BaseModel):
    """Survey response with associated chat metadata"""
    survey: SurveyResponse
    chat_query: str
    chat_preview: str
    chat_timestamp: datetime


class SurveyStats(BaseModel):
    """Aggregated survey statistics"""
    total_surveys: int
    avg_answer_quality: float
    avg_answer_clarity: float
    avg_answer_completeness: float
    avg_citations_relevance: float
    avg_citations_accuracy: float
    avg_balance_perception: float
    avg_balance_fairness: float
    avg_compass_usefulness: float
    avg_experts_usefulness: float
    avg_baseline_improvement: float
    avg_authority_value: float
    avg_citation_pipeline_value: float
    avg_overall_satisfaction: float
    recommendation_rate: float  # % who would recommend

    # Score breakdown
    scores_distribution: Dict[str, Dict[int, int]]  # metric -> {score: count}


class SurveyListResponse(BaseModel):
    """Response for listing surveys"""
    surveys: List[SurveyWithChat]
    total: int
    stats: Optional[SurveyStats] = None


# Survey questions configuration (for frontend)
SURVEY_QUESTIONS = [
    {
        "id": "answer_quality",
        "category": "Qualità Risposta",
        "question": "Come valuti la qualità complessiva della risposta?",
        "description": "Considera l'utilità pratica per il tuo lavoro giornalistico"
    },
    {
        "id": "answer_clarity",
        "category": "Qualità Risposta",
        "question": "Quanto è chiara e leggibile la risposta?",
        "description": "Valuta la struttura, il linguaggio e la facilità di comprensione"
    },
    {
        "id": "answer_completeness",
        "category": "Qualità Risposta",
        "question": "La risposta copre tutti gli aspetti rilevanti?",
        "description": "Considera se mancano informazioni importanti"
    },
    {
        "id": "citations_relevance",
        "category": "Citazioni",
        "question": "Le citazioni parlamentari sono pertinenti?",
        "description": "Valuta se le citazioni supportano effettivamente la risposta"
    },
    {
        "id": "citations_accuracy",
        "category": "Citazioni",
        "question": "Le attribuzioni delle citazioni sono accurate?",
        "description": "Considera se deputato, data e contesto sono corretti"
    },
    {
        "id": "balance_perception",
        "category": "Bilanciamento Politico",
        "question": "Percepisci un adeguato bilanciamento politico?",
        "description": "Valuta se sono rappresentate diverse posizioni politiche"
    },
    {
        "id": "balance_fairness",
        "category": "Bilanciamento Politico",
        "question": "Le diverse posizioni sono trattate equamente?",
        "description": "Considera se c'è imparzialità nella presentazione"
    },
    {
        "id": "compass_usefulness",
        "category": "Funzionalità",
        "question": "La bussola ideologica è utile per comprendere le posizioni?",
        "description": "Valuta se la visualizzazione aiuta l'analisi"
    },
    {
        "id": "experts_usefulness",
        "category": "Funzionalità",
        "question": "L'identificazione degli esperti è utile?",
        "description": "Considera se aiuta a identificare le voci autorevoli sul tema"
    },
    {
        "id": "baseline_improvement",
        "category": "Confronto Baseline",
        "question": "Quanto ritieni che il sistema sia migliore di un RAG standard?",
        "description": "Confronta con un sistema che non ha authority scoring, compass ideologico e verifica citazioni"
    },
    {
        "id": "authority_value",
        "category": "Confronto Baseline",
        "question": "Quanto valore aggiunge il sistema di authority scoring?",
        "description": "Valuta se la selezione degli esperti per competenza migliora la qualità rispetto a una selezione casuale"
    },
    {
        "id": "citation_pipeline_value",
        "category": "Confronto Baseline",
        "question": "Quanto valore aggiunge la pipeline di verifica citazioni?",
        "description": "Valuta se la verifica offset-based delle citazioni migliora l'affidabilità rispetto al fuzzy matching"
    },
    {
        "id": "overall_satisfaction",
        "category": "Valutazione Complessiva",
        "question": "Qual è la tua soddisfazione complessiva?",
        "description": "Valutazione generale dell'esperienza"
    }
]
