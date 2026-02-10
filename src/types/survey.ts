/**
 * Survey types for user evaluation of ParliamentRAG responses.
 */

export interface SurveyQuestion {
  id: string;
  category: string;
  question: string;
  description: string;
}

export interface SurveyResponse {
  id: string;
  chat_id: string;
  timestamp: string;

  // Core evaluation metrics (1-5 scale)
  answer_quality: number;
  answer_clarity: number;
  answer_completeness: number;

  // Citations evaluation
  citations_relevance: number;
  citations_accuracy: number;

  // Political balance evaluation
  balance_perception: number;
  balance_fairness: number;

  // Feature-specific evaluations
  compass_usefulness: number;
  experts_usefulness: number;

  // Baseline comparison
  baseline_improvement: number;
  authority_value: number;
  citation_pipeline_value: number;

  // Overall satisfaction
  overall_satisfaction: number;
  would_recommend: boolean;

  // Qualitative feedback
  feedback_positive?: string;
  feedback_improvement?: string;

  // Metadata
  evaluator_role?: string;
  evaluation_context?: string;
}

export interface SurveyResponseCreate {
  chat_id: string;

  answer_quality: number;
  answer_clarity: number;
  answer_completeness: number;

  citations_relevance: number;
  citations_accuracy: number;

  balance_perception: number;
  balance_fairness: number;

  compass_usefulness: number;
  experts_usefulness: number;

  baseline_improvement: number;
  authority_value: number;
  citation_pipeline_value: number;

  overall_satisfaction: number;
  would_recommend: boolean;

  feedback_positive?: string;
  feedback_improvement?: string;

  evaluator_role?: string;
  evaluation_context?: string;
}

export interface SurveyWithChat {
  survey: SurveyResponse;
  chat_query: string;
  chat_preview: string;
  chat_timestamp: string;
}

export interface SurveyStats {
  total_surveys: number;
  avg_answer_quality: number;
  avg_answer_clarity: number;
  avg_answer_completeness: number;
  avg_citations_relevance: number;
  avg_citations_accuracy: number;
  avg_balance_perception: number;
  avg_balance_fairness: number;
  avg_compass_usefulness: number;
  avg_experts_usefulness: number;
  avg_baseline_improvement: number;
  avg_authority_value: number;
  avg_citation_pipeline_value: number;
  avg_overall_satisfaction: number;
  recommendation_rate: number;
  scores_distribution: Record<string, Record<number, number>>;
}

export interface SurveyListResponse {
  surveys: SurveyWithChat[];
  total: number;
  stats?: SurveyStats;
}

export interface PendingChat {
  id: string;
  query: string;
  preview: string;
  timestamp: string;
}

export interface PendingChatsResponse {
  pending: PendingChat[];
  total: number;
}

// Survey form state
export interface SurveyFormState {
  answer_quality: number;
  answer_clarity: number;
  answer_completeness: number;
  citations_relevance: number;
  citations_accuracy: number;
  balance_perception: number;
  balance_fairness: number;
  compass_usefulness: number;
  experts_usefulness: number;
  baseline_improvement: number;
  authority_value: number;
  citation_pipeline_value: number;
  overall_satisfaction: number;
  would_recommend: boolean;
  feedback_positive: string;
  feedback_improvement: string;
}

// Survey questions configuration
export const SURVEY_QUESTIONS: SurveyQuestion[] = [
  {
    id: "answer_quality",
    category: "Qualità Risposta",
    question: "Come valuti la qualità complessiva della risposta?",
    description: "Considera l'utilità pratica per il tuo lavoro giornalistico",
  },
  {
    id: "answer_clarity",
    category: "Qualità Risposta",
    question: "Quanto è chiara e leggibile la risposta?",
    description: "Valuta la struttura, il linguaggio e la facilità di comprensione",
  },
  {
    id: "answer_completeness",
    category: "Qualità Risposta",
    question: "La risposta copre tutti gli aspetti rilevanti?",
    description: "Considera se mancano informazioni importanti",
  },
  {
    id: "citations_relevance",
    category: "Citazioni",
    question: "Le citazioni parlamentari sono pertinenti?",
    description: "Valuta se le citazioni supportano effettivamente la risposta",
  },
  {
    id: "citations_accuracy",
    category: "Citazioni",
    question: "Le attribuzioni delle citazioni sono accurate?",
    description: "Considera se deputato, data e contesto sono corretti",
  },
  {
    id: "balance_perception",
    category: "Bilanciamento Politico",
    question: "Percepisci un adeguato bilanciamento politico?",
    description: "Valuta se sono rappresentate diverse posizioni politiche",
  },
  {
    id: "balance_fairness",
    category: "Bilanciamento Politico",
    question: "Le diverse posizioni sono trattate equamente?",
    description: "Considera se c'è imparzialità nella presentazione",
  },
  {
    id: "compass_usefulness",
    category: "Funzionalità",
    question: "La bussola ideologica è utile per comprendere le posizioni?",
    description: "Valuta se la visualizzazione aiuta l'analisi",
  },
  {
    id: "experts_usefulness",
    category: "Funzionalità",
    question: "L'identificazione degli esperti è utile?",
    description: "Considera se aiuta a identificare le voci autorevoli sul tema",
  },
  {
    id: "baseline_improvement",
    category: "Confronto Baseline",
    question: "Quanto ritieni che il sistema sia migliore di un RAG standard?",
    description: "Confronta con un sistema che non ha authority scoring, compass ideologico e verifica citazioni",
  },
  {
    id: "authority_value",
    category: "Confronto Baseline",
    question: "Quanto valore aggiunge il sistema di authority scoring?",
    description: "Valuta se la selezione degli esperti per competenza migliora la qualità rispetto a una selezione casuale",
  },
  {
    id: "citation_pipeline_value",
    category: "Confronto Baseline",
    question: "Quanto valore aggiunge la pipeline di verifica citazioni?",
    description: "Valuta se la verifica offset-based delle citazioni migliora l'affidabilità rispetto al fuzzy matching",
  },
  {
    id: "overall_satisfaction",
    category: "Valutazione Complessiva",
    question: "Qual è la tua soddisfazione complessiva?",
    description: "Valutazione generale dell'esperienza",
  },
];

// Initial form state
export const getInitialSurveyFormState = (): SurveyFormState => ({
  answer_quality: 0,
  answer_clarity: 0,
  answer_completeness: 0,
  citations_relevance: 0,
  citations_accuracy: 0,
  balance_perception: 0,
  balance_fairness: 0,
  compass_usefulness: 0,
  experts_usefulness: 0,
  baseline_improvement: 0,
  authority_value: 0,
  citation_pipeline_value: 0,
  overall_satisfaction: 0,
  would_recommend: false,
  feedback_positive: "",
  feedback_improvement: "",
});
