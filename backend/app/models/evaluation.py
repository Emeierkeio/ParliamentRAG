"""
Evaluation models for automated and A/B comparison assessment of ParliamentRAG responses.
Designed for scientific evaluation in thesis/paper context.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime

from .survey import SurveyResponse, SurveyStats, SimpleRatingResponse


class AutomatedMetrics(BaseModel):
    """Automated metrics computed from a single chat's stored pipeline data."""
    chat_id: str

    # Party Coverage: unique parties in citations / 10 known groups
    party_coverage_score: float = Field(..., ge=0, le=1)
    parties_represented: int
    parties_total: int = 10
    party_breakdown: Dict[str, int] = {}

    citations_total: int

    # Citation Fidelity: citations whose text appears verbatim in source chunk / total citations
    # (combines integrity check + verbatim match into a single end-to-end metric)
    verbatim_match_score: float = Field(..., ge=0, le=1)
    verbatim_match_count: int = 0

    # Response Completeness: sections (## headers) / 10 parties
    response_completeness: float = Field(..., ge=0, le=1)

    # Authority Utilization: mean authority_score of cited experts
    authority_utilization: float = Field(..., ge=0, le=1)
    experts_count: int = 0

    # Authority Discrimination: std of authority scores (higher = more selective)
    authority_discrimination: float = Field(..., ge=0)

    # Per-group authority breakdown (system)
    authority_by_group: Dict[str, float] = {}

    # Per-chat baseline authority comparison
    baseline_authority: Optional[float] = None
    baseline_authority_by_group: Optional[Dict[str, float]] = None

    # Global authority spread across all deputies for this topic (from evaluation_set.json)
    authority_spread_stats: Optional[Dict[str, Any]] = None


class AggregatedMetrics(BaseModel):
    """Aggregated automated metrics across all evaluated chats."""
    total_chats: int
    avg_party_coverage: float
    avg_verbatim_match: float
    avg_response_completeness: float
    avg_authority_utilization: float
    avg_authority_discrimination: float

    # 95% Confidence intervals (lower, upper)
    ci_party_coverage: Tuple[float, float]
    ci_verbatim_match: Tuple[float, float]
    ci_response_completeness: Tuple[float, float]
    ci_authority_utilization: Tuple[float, float]
    ci_authority_discrimination: Tuple[float, float]

    # Baseline comparison metrics (computed from evaluation_set.json)
    avg_baseline_party_coverage: Optional[float] = None
    avg_baseline_citation_fidelity: Optional[float] = None
    avg_baseline_response_completeness: Optional[float] = None
    avg_baseline_authority: Optional[float] = None
    ci_baseline_party_coverage: Optional[Tuple[float, float]] = None
    ci_baseline_citation_fidelity: Optional[Tuple[float, float]] = None
    ci_baseline_response_completeness: Optional[Tuple[float, float]] = None
    ci_baseline_authority: Optional[Tuple[float, float]] = None

    # Aggregate baseline authority per parliamentary group (average across chats that have it)
    avg_baseline_authority_by_group: Optional[Dict[str, float]] = None


class CombinedEvaluation(BaseModel):
    """Combined human + automated evaluation for a single chat."""
    chat_id: str
    chat_query: str
    timestamp: str
    automated: AutomatedMetrics
    human: Optional[SurveyResponse] = None         # A/B blind evaluation
    human_simple: Optional[SimpleRatingResponse] = None  # Simple Likert evaluation


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

    # Per-group authority preference (de-blinded): party_key → {system: N, equal: N, baseline: N}
    group_authority_preference: Optional[Dict[str, Dict[str, int]]] = None


class EvaluationDashboardData(BaseModel):
    """Full dashboard payload combining automated and human evaluation."""
    automated_aggregate: AggregatedMetrics
    human_aggregate: Optional[SurveyStats] = None
    ab_comparison: Optional[ABComparisonStats] = None
    per_chat: List[CombinedEvaluation]
    total_chats: int
    total_evaluated: int
    total_simple_rated: int = 0
