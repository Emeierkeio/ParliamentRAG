/**
 * Types for the chat system
 */
import type { CompassData } from "@/components/chat/CompassCard";

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
  photo?: string;
  speaker_id?: string;
  vote_count?: number;
  committee?: string;
  session_number?: number;
  debate_title?: string;
  institutional_role?: string | null;
}

export interface Expert {
  id: string;
  first_name: string;
  last_name: string;
  group: string;
  photo?: string;
  camera_profile_url?: string;
  profession?: string;
  education?: string;
  committee?: string;
  committees?: string[];
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
  photo?: string;
  profession?: string;
  education?: string;
  committee?: string;
  institutional_role?: string;
}

export interface InterventionDetail {
  speech_id: string;
  speaker_id?: string;
  speaker_name: string;
  party: string;
  coalition: string;
  date: string;
  debate_title: string;
  session_number: number;
  photo?: string;
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
  // Optional metadata for assistant responses
  citations?: Citation[];
  experts?: Expert[];
  committeeMatches?: Array<{ nome: string; score: number; matched_keywords: string[]; categories: string[] }>;
  compass?: CompassData;
  balanceMetrics?: BalanceMetrics;
  hqMetadata?: HQMetadata;
  topicStats?: TopicStatistics;
  // History ID for sharing
  chatId?: string;
}

export interface BalanceMetrics {
  majorityPercentage: number;
  oppositionPercentage: number;
  biasScore: number; // -1 = all opposition, 0 = balanced, 1 = all majority
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
  details?: Record<string, unknown>;
}

export interface ChatHistoryItem {
  id: string;
  query: string;
  answer: string;
  timestamp: string;
  preview?: string;
  experts?: Expert[];
  citations?: Citation[];
  steps?: StepResult[];
  balance?: {
    maggioranza_percentage: number;
    opposizione_percentage: number;
    bias_score: number;
  };
  compass?: CompassData;
  commissioni?: Array<{ nome: string; score: number; matched_keywords: string[]; categories: string[] }>;
  hq_variants?: HQVariant[];
  topic_stats?: TopicStatistics;
}

export interface ProcessingProgress {
  currentStep: number;
  totalSteps: number;
  stepLabel: string;
  stepDescription: string;
  isComplete: boolean;
  stepResults: StepResult[];
  isWaiting?: boolean;
  waitingMessage?: string;
  queuePosition?: number;   // position in queue (1 = next)
  aheadCount?: number;      // number of people ahead of this user (= position - 1)
  activeCount?: number;     // pipelines currently running
  elapsedSeconds?: number;  // seconds spent waiting so far
}
