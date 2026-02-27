/**
 * Survey types for A/B blind evaluation of ParliamentRAG vs Baseline RAG.
 */

export interface SurveyQuestion {
  id: string;
  category: string;
  question: string;
  description: string;
}

export interface ABRating {
  rating_a: number;
  rating_b: number;
  preference: "A" | "B" | "equal" | "";
}

export interface CitationEvaluation {
  evidence_id: string;
  relevance: number;      // 1-5
  faithfulness: number;    // 1-5
  informativeness: number; // 1-5
  attribution: "correct" | "incorrect" | "unverifiable" | "";
  issues: string[];
}

export const CITATION_ISSUES = [
  { id: "none", label: "Nessun problema", icon: "check" },
  { id: "out_of_context", label: "Fuori contesto", icon: "alert" },
  { id: "truncated", label: "Citazione troncata", icon: "scissors" },
  { id: "wrong_attribution", label: "Attribuzione errata", icon: "user-x" },
  { id: "duplicate", label: "Duplicata", icon: "copy" },
  { id: "unverifiable", label: "Non verificabile", icon: "help" },
] as const;

export const getInitialCitationEvaluation = (evidenceId: string): CitationEvaluation => ({
  evidence_id: evidenceId,
  relevance: 0,
  faithfulness: 0,
  informativeness: 0,
  attribution: "",
  issues: [],
});

export interface SurveyResponse {
  id: string;
  chat_id: string;
  timestamp: string;

  // A/B comparative ratings per dimension
  answer_quality: ABRating;
  answer_clarity: ABRating;
  answer_completeness: ABRating;
  citations_relevance: ABRating;
  citations_accuracy: ABRating;
  balance_perception: ABRating;
  balance_fairness: ABRating;

  // Overall
  overall_satisfaction_a: number;
  overall_satisfaction_b: number;
  overall_preference: "A" | "B" | "equal";

  would_recommend: boolean;

  // Qualitative feedback
  feedback_positive?: string;
  feedback_improvement?: string;

  // Individual citation evaluations
  citation_evaluations_a: CitationEvaluation[];
  citation_evaluations_b: CitationEvaluation[];

  // Metadata
  evaluator_role?: string;
  evaluation_context?: string;
  evaluator_id?: string;
}

export interface SurveyResponseCreate {
  chat_id: string;

  answer_quality: ABRating;
  answer_clarity: ABRating;
  answer_completeness: ABRating;
  citations_relevance: ABRating;
  citations_accuracy: ABRating;
  balance_perception: ABRating;
  balance_fairness: ABRating;
  source_relevance: ABRating;
  source_authority: ABRating;
  source_coverage: ABRating;

  overall_satisfaction_a: number;
  overall_satisfaction_b: number;
  overall_preference: "A" | "B" | "equal";

  would_recommend: boolean;

  feedback_positive?: string;
  feedback_improvement?: string;

  citation_evaluations_a?: CitationEvaluation[];
  citation_evaluations_b?: CitationEvaluation[];

  evaluator_role?: string;
  evaluation_context?: string;
  evaluator_id?: string;

  // For evaluation_set A/B flow: frontend-generated assignment stored on ChatHistory
  ab_assignment?: Record<string, string>; // e.g. { A: "system", B: "baseline" }
  evaluation_set_topic?: string;

  // Baseline authority: mean authority score of experts found in baseline response
  baseline_authority_avg?: number;

  // Per-group authority votes: group_key → -1 (A better), 0 (equal/same), 1 (B better)
  group_authority_votes?: Record<string, number>;
}

export interface SurveyWithChat {
  survey: SurveyResponse;
  chat_query: string;
  chat_preview: string;
  chat_timestamp: string;
}

export interface SurveyStats {
  total_surveys: number;
  system_avg_per_dimension: Record<string, number>;
  baseline_avg_per_dimension: Record<string, number>;
  system_avg_overall: number;
  baseline_avg_overall: number;
  system_win_rate: number;
  baseline_win_rate: number;
  tie_rate: number;
  per_dimension_preference: Record<string, Record<string, number>>;
  recommendation_rate: number;
}

export interface SurveyListResponse {
  surveys: SurveyWithChat[];
  total: number;
  stats?: SurveyStats;
}

export interface SimpleRatingResponse {
  id: string;
  chat_id: string;
  timestamp: string;
  answer_clarity: number;
  answer_quality: number;
  balance_perception: number;
  balance_fairness: number;
  feedback?: string;
  evaluator_id?: string;
}

export interface SimpleRatingCreate {
  chat_id: string;
  answer_clarity: number;
  answer_quality: number;
  balance_perception: number;
  balance_fairness: number;
  feedback?: string;
  evaluator_id?: string;
}

export const SIMPLE_DIMENSIONS = [
  "answer_clarity",
  "answer_quality",
  "balance_perception",
  "balance_fairness",
] as const;

export type SimpleDimension = typeof SIMPLE_DIMENSIONS[number];

export const SIMPLE_DIMENSION_LABELS: Record<SimpleDimension, string> = {
  answer_clarity: "Chiarezza espositiva",
  answer_quality: "Qualita complessiva percepita",
  balance_perception: "Bilanciamento percepito",
  balance_fairness: "Equita rappresentazione",
};

export interface SimpleRatingFormState {
  answer_clarity: number;
  answer_quality: number;
  balance_perception: number;
  balance_fairness: number;
  feedback: string;
}

export const getInitialSimpleRatingFormState = (): SimpleRatingFormState => ({
  answer_clarity: 0,
  answer_quality: 0,
  balance_perception: 0,
  balance_fairness: 0,
  feedback: "",
});

export interface BaselineCitation {
  speaker: string;
  group: string;
  date: string;
  quote: string;
  verbatim_verified: boolean;
}

export interface PendingChat {
  id: string;
  query: string;
  preview: string;
  timestamp: string;
  evaluation_type: "ab" | "simple";
  matched_topic?: string;
  baseline_answer?: string;
  baseline_experts?: any[];
  baseline_citations?: BaselineCitation[];
}

export interface PendingChatsResponse {
  pending: PendingChat[];
  total: number;
}

// A/B dimensions for comparison
export const AB_DIMENSIONS = [
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
] as const;

export type ABDimension = typeof AB_DIMENSIONS[number];

// Survey form state for A/B evaluation
export interface SurveyFormState {
  answer_quality: ABRating;
  answer_clarity: ABRating;
  answer_completeness: ABRating;
  citations_relevance: ABRating;
  citations_accuracy: ABRating;
  balance_perception: ABRating;
  balance_fairness: ABRating;
  // Source authority dimensions (grounded in TREC Expert Finding + DQI literature)
  source_relevance: ABRating;
  source_authority: ABRating;
  source_coverage: ABRating;
  overall_satisfaction_a: number;
  overall_satisfaction_b: number;
  overall_preference: "A" | "B" | "equal" | "";
  would_recommend: boolean;
  feedback_positive: string;
  feedback_improvement: string;
  citation_evaluations_a: CitationEvaluation[];
  citation_evaluations_b: CitationEvaluation[];
}

// Survey questions configuration - A/B format
export const SURVEY_QUESTIONS: SurveyQuestion[] = [
  {
    id: "answer_quality",
    category: "Qualita Risposta",
    question: "Qualita complessiva della risposta",
    description: "Considera l'utilita pratica per il lavoro giornalistico",
  },
  {
    id: "answer_clarity",
    category: "Qualita Risposta",
    question: "Chiarezza e leggibilita della risposta",
    description: "Valuta la struttura, il linguaggio e la facilita di comprensione",
  },
  {
    id: "answer_completeness",
    category: "Qualita Risposta",
    question: "Completezza delle informazioni",
    description: "Considera se mancano informazioni importanti",
  },
  {
    id: "citations_relevance",
    category: "Citazioni",
    question: "Pertinenza delle citazioni parlamentari",
    description: "Valuta se le citazioni supportano effettivamente la risposta",
  },
  {
    id: "citations_accuracy",
    category: "Citazioni",
    question: "Accuratezza delle attribuzioni",
    description: "Considera se deputato, data e contesto sono corretti",
  },
  {
    id: "balance_perception",
    category: "Bilanciamento Politico",
    question: "Bilanciamento politico percepito",
    description: "Valuta se sono rappresentate diverse posizioni politiche",
  },
  {
    id: "balance_fairness",
    category: "Bilanciamento Politico",
    question: "Equita nella rappresentazione",
    description: "Considera se c'e imparzialita nella presentazione",
  },
  // Authority dimensions — Autorità Esperti category
  // Based on: TREC Expert Finding (Craswell et al. 2005), DQI (Steenbergen et al. 2003),
  // Source Credibility Theory (Hovland et al. 1953; Gaziano & McGrath 1986)
  {
    id: "source_relevance",
    category: "Autorità Esperti",
    question: "Rilevanza tematica degli esperti",
    description: "Gli esperti citati sono le voci parlamentari più attive e pertinenti su questo tema?",
  },
  {
    id: "source_authority",
    category: "Autorità Esperti",
    question: "Autorevolezza istituzionale",
    description: "Le figure citate ricoprono ruoli rilevanti (presidenze di commissione, portavoce, governo)?",
  },
  {
    id: "source_coverage",
    category: "Autorità Esperti",
    question: "Copertura delle coalizioni",
    description: "Le principali forze politiche sono rappresentate in modo equilibrato tra maggioranza e opposizione?",
  },
  {
    id: "overall_satisfaction",
    category: "Valutazione Complessiva",
    question: "Soddisfazione complessiva",
    description: "Valutazione generale dell'esperienza con ciascuna risposta",
  },
];

// Initial form state
export const getInitialABRating = (): ABRating => ({
  rating_a: 0,
  rating_b: 0,
  preference: "",
});

export const getInitialSurveyFormState = (): SurveyFormState => ({
  answer_quality: getInitialABRating(),
  answer_clarity: getInitialABRating(),
  answer_completeness: getInitialABRating(),
  citations_relevance: getInitialABRating(),
  citations_accuracy: getInitialABRating(),
  balance_perception: getInitialABRating(),
  balance_fairness: getInitialABRating(),
  source_relevance: getInitialABRating(),
  source_authority: getInitialABRating(),
  source_coverage: getInitialABRating(),
  overall_satisfaction_a: 0,
  overall_satisfaction_b: 0,
  overall_preference: "",
  would_recommend: false,
  feedback_positive: "",
  feedback_improvement: "",
  citation_evaluations_a: [],
  citation_evaluations_b: [],
});
