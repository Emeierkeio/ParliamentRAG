"""
Evaluation models for automated and A/B comparison assessment of ParliamentRAG responses.
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


class ABComparisonStats(BaseModel):
    """Aggregated A/B comparison results from human evaluations (de-blinded)."""
    total_evaluations: int

    system_win_rate: float   # % of overall preferences favoring system
    baseline_win_rate: float  # % of overall preferences favoring baseline
    tie_rate: float           # % equal

    system_avg_ratings: Dict[str, float]   # dimension -> avg rating for system
    baseline_avg_ratings: Dict[str, float]  # dimension -> avg rating for baseline

    system_avg_overall: float
    baseline_avg_overall: float

    per_dimension_preference: Dict[str, Dict[str, int]]  # dim -> {system: N, baseline: N, equal: N}


class EvaluationDashboardData(BaseModel):
    """Full dashboard payload combining automated and human evaluation."""
    automated_aggregate: AggregatedMetrics
    human_aggregate: Optional[SurveyStats] = None
    ab_comparison: Optional[ABComparisonStats] = None
    per_chat: List[CombinedEvaluation]
    total_chats: int
    total_evaluated: int
