/**
 * Evaluation types for scientific assessment of ParliamentRAG.
 */

import type { SurveyResponse, SurveyStats } from "./survey";

export interface AutomatedMetrics {
  chat_id: string;

  party_coverage_score: number;
  parties_represented: number;
  parties_total: number;
  party_breakdown: Record<string, number>;

  citation_integrity_score: number;
  citations_valid: number;
  citations_total: number;

  balance_score: number;
  maggioranza_pct: number;
  opposizione_pct: number;

  authority_utilization: number;
  experts_count: number;

  response_completeness: number;
}

export interface AggregatedMetrics {
  total_chats: number;
  avg_party_coverage: number;
  avg_citation_integrity: number;
  avg_balance_score: number;
  avg_authority_utilization: number;
  avg_response_completeness: number;

  ci_party_coverage: [number, number];
  ci_citation_integrity: [number, number];
  ci_balance_score: [number, number];
  ci_authority_utilization: [number, number];
  ci_response_completeness: [number, number];
}

export interface CombinedEvaluation {
  chat_id: string;
  chat_query: string;
  timestamp: string;
  automated: AutomatedMetrics;
  human: SurveyResponse | null;
}

export interface ABComparisonStats {
  total_evaluations: number;
  system_win_rate: number;
  baseline_win_rate: number;
  tie_rate: number;
  system_avg_ratings: Record<string, number>;
  baseline_avg_ratings: Record<string, number>;
  system_avg_overall: number;
  baseline_avg_overall: number;
  per_dimension_preference: Record<string, Record<string, number>>;
}

export interface EvaluationDashboardData {
  automated_aggregate: AggregatedMetrics;
  human_aggregate: SurveyStats | null;
  ab_comparison: ABComparisonStats | null;
  per_chat: CombinedEvaluation[];
  total_chats: number;
  total_evaluated: number;
}
