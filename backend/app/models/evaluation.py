"""
Evaluation models for automated and combined assessment of ParliamentRAG responses.
Designed for scientific evaluation in thesis/paper context.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from .survey import SurveyResponse, SurveyStats


class AutomatedMetrics(BaseModel):
    """Automated metrics computed from a single chat's stored pipeline data."""
    chat_id: str

    # Party Coverage: unique parties in citations / 10 known groups
    party_coverage_score: float = Field(..., ge=0, le=1)
    parties_represented: int
    parties_total: int = 10
    party_breakdown: Dict[str, int] = {}

    # Citation Integrity: citations with valid quote_text / total
    citation_integrity_score: float = Field(..., ge=0, le=1)
    citations_valid: int
    citations_total: int

    # Balance: 1 - bias_score
    balance_score: float = Field(..., ge=0, le=1)
    maggioranza_pct: float = 0
    opposizione_pct: float = 0

    # Authority Utilization: mean authority_score of cited experts
    authority_utilization: float = Field(..., ge=0, le=1)
    experts_count: int = 0

    # Response Completeness: sections (## headers) / 10 parties
    response_completeness: float = Field(..., ge=0, le=1)


class AggregatedMetrics(BaseModel):
    """Aggregated automated metrics across all evaluated chats."""
    total_chats: int
    avg_party_coverage: float
    avg_citation_integrity: float
    avg_balance_score: float
    avg_authority_utilization: float
    avg_response_completeness: float

    # 95% Confidence intervals (lower, upper)
    ci_party_coverage: Tuple[float, float]
    ci_citation_integrity: Tuple[float, float]
    ci_balance_score: Tuple[float, float]
    ci_authority_utilization: Tuple[float, float]
    ci_response_completeness: Tuple[float, float]


class CombinedEvaluation(BaseModel):
    """Combined human + automated evaluation for a single chat."""
    chat_id: str
    chat_query: str
    timestamp: str
    automated: AutomatedMetrics
    human: Optional[SurveyResponse] = None


class BaselineComparison(BaseModel):
    """
    Baseline reference values for a standard RAG/LLM system
    WITHOUT authority scoring, ideological compass, or citation correction.

    Values derived from RAG evaluation literature:
    - Citation integrity: standard RAG with fuzzy matching ~60-70%
    - Party coverage: dense retrieval without diversity enforcement ~30-40%
    - Balance: no coalition-aware retrieval, majority-dominated ~55-65% bias
    - Authority: no scoring, equal weight = ~0.5 random
    - Completeness: no per-party sectional writing ~20-30%
    """
    party_coverage: float = Field(default=0.35, description="Dense retrieval without diversity enforcement")
    citation_integrity: float = Field(default=0.65, description="RAG with fuzzy matching, no offset verification")
    balance_score: float = Field(default=0.60, description="No coalition-aware retrieval")
    authority_utilization: float = Field(default=0.50, description="No authority scoring, random selection")
    response_completeness: float = Field(default=0.25, description="No per-party sectional generation")

    label: str = "Naive RAG (senza authority/compass/citation pipeline)"


class EvaluationDashboardData(BaseModel):
    """Full dashboard payload combining automated and human evaluation."""
    automated_aggregate: AggregatedMetrics
    human_aggregate: Optional[SurveyStats] = None
    baseline: BaselineComparison = Field(default_factory=BaselineComparison)
    per_chat: List[CombinedEvaluation]
    total_chats: int
    total_evaluated: int
