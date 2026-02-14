/**
 * Tipi per il sistema di chat
 */

export type MessageRole = "user" | "assistant" | "system";

export type MessageStatus = "sending" | "streaming" | "complete" | "error";

export interface Citation {
  chunk_id: string;
  deputy_first_name: string;
  deputy_last_name: string;
  group: string;
  coalition: string;
  text?: string;
  quote_text?: string;
  full_text?: string;
  date: string;
  similarity: number;
  debate?: string;
  debate_id?: string;
  intervention_id?: string;
  camera_profile_url?: string;
  [key: string]: any;
}

export interface Expert {
  id: string;
  first_name: string;
  last_name: string;
  group: string;
  camera_profile_url?: string;
  profession?: string;
  education?: string;
  committee?: string;
  institutional_role?: string;
  coalition: string;
  authority_score: number;
  score_breakdown?: {
    speeches: number;
    acts: number;
    committee: number;
    profession: number;
    education: number;
    role: number;
  };
  relevant_speeches_count: number;
  acts_detail?: Array<{
    title: string;
    eurovoc: string;
    is_primary: boolean;
    similarity: number;
  }>;
}

export interface HQVariant {
  index: number;
  text: string;
  score: number;
  is_best: boolean;
  temperature: number;
}

export interface HQMetadata {
  judge_reason: string;
  variants: HQVariant[];
}

export interface SpeakerDetail {
  speaker_id: string;
  speaker_name: string;
  party: string;
  coalition: string;
  intervention_count: number;
  camera_profile_url?: string;
  profession?: string;
  education?: string;
  committee?: string;
  institutional_role?: string;
}

export interface InterventionDetail {
  speech_id: string;
  speaker_name: string;
  party: string;
  coalition: string;
  date: string;
  debate_title: string;
  session_number: number;
}

export interface SessionDetail {
  session_number: number;
  date: string;
  debate_title: string;
}

export interface TopicStatistics {
  intervention_count: number;
  speaker_count: number;
  first_date: string;
  last_date: string;
  speakers_detail: SpeakerDetail[];
  interventions_detail: InterventionDetail[];
  sessions_detail: SessionDetail[];
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  status: MessageStatus;
  // Metadati opzionali per le risposte dell'assistente
  citations?: Citation[];
  experts?: Expert[];
  compass?: any; // CompassData
  balanceMetrics?: BalanceMetrics;
  hqMetadata?: HQMetadata;
  topicStats?: TopicStatistics;
  // A/B baseline comparison
  baselineAnswer?: string;
  abAssignment?: Record<string, string>; // e.g. {"A": "system", "B": "baseline"}
  // History ID for sharing
  chatId?: string;
}

export interface BalanceMetrics {
  maggioranzaPercentage: number;
  opposizionePercentage: number;
  biasScore: number; // -1 = tutto opposizione, 0 = bilanciato, 1 = tutto maggioranza
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

// Progress tracking
export interface StepResult {
  step: number;
  label: string;
  result?: string;
  details?: any;
}

export interface ProcessingProgress {
  currentStep: number;
  totalSteps: number;
  stepLabel: string;
  stepDescription: string;
  isComplete: boolean;
  stepResults: StepResult[];
}
