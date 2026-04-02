/**
 * SSE event payload interfaces derived from SSE_CONTRACT.md.
 * Field names match the frozen wire contract — do not rename without a coordinated backend change.
 */

import type {
  Expert,
  Citation,
  SpeakerDetail,
  InterventionDetail,
  SessionDetail,
  HQVariant,
} from "./chat";
import type { CompassData } from "../components/chat/CompassCard";

export interface CommissionItem {
  name: string;
  nome?: string;
  score?: number;
  matched_keywords?: string[];
  categories?: string[];
  url?: string;
}

// ── chat.py pipeline events ────────────────────────────────────────────────

export interface SSEWaitingEvent {
  type: "waiting";
  queue_position?: number;
  ahead_count?: number;
  active_count?: number;
  elapsed_seconds?: number;
  message?: string;
}

export interface SSEProgressEvent {
  type: "progress";
  step: number;
  total?: number;
  message: string;
}

/** Experts event from chat.py — payload key is `experts` */
export interface SSEExpertsChatEvent {
  type: "experts";
  experts: Expert[];
}

/** Experts event from query.py — payload key is `data` */
export interface SSEExpertsQueryEvent {
  type: "experts";
  data: Expert[];
}

/** Chunk event from chat.py — payload key is `content` */
export interface SSEChunkChatEvent {
  type: "chunk";
  content: string;
}

/** Chunk event from query.py — payload key is `data` */
export interface SSEChunkQueryEvent {
  type: "chunk";
  data: string;
}

/** Citations event from chat.py — payload key is `citations` */
export interface SSECitationsChatEvent {
  type: "citations";
  citations: Citation[];
}

/** Citations event from query.py — payload key is `data` */
export interface SSECitationsQueryEvent {
  type: "citations";
  data: Citation[];
}

export interface SSECommissioniEvent {
  type: "commissioni";
  commissioni: CommissionItem[];
}

/** Balance event — only emitted by chat.py pipeline. Wire names are frozen. */
export interface SSEBalanceEvent {
  type: "balance";
  maggioranza_percentage: number;
  opposizione_percentage: number;
  bias_score: number;
}

/** Compass event from chat.py — direct fields (no wrapper) */
export interface SSECompassChatEvent {
  type: "compass";
  meta: CompassData["meta"];
  axes: CompassData["axes"];
  groups: CompassData["groups"];
  scatter_sample: CompassData["scatter_sample"];
}

/** Compass event from query.py — wrapped in `data` */
export interface SSECompassQueryEvent {
  type: "compass";
  data: CompassData;
}

export interface SSETopicStatsEvent {
  type: "topic_stats";
  intervention_count: number;
  speaker_count: number;
  first_date: string;
  last_date: string;
  speakers_detail: SpeakerDetail[];
  interventions_detail: InterventionDetail[];
  sessions_detail: SessionDetail[];
}

export interface SSECitationDetailsEvent {
  type: "citation_details";
  citations: Citation[];
}

export interface SSEHQVariantsEvent {
  type: "hq_variants";
  variants: HQVariant[];
}

export interface SSECompleteEvent {
  type: "complete";
  metadata?: {
    timing?: Record<string, number>;
    dense_channel_count?: number;
    graph_channel_count?: number;
    [key: string]: unknown;
  };
}

export interface SSEErrorEvent {
  type: "error";
  message: string;
}

export type SSEEvent =
  | SSEWaitingEvent
  | SSEProgressEvent
  | SSEExpertsChatEvent
  | SSEExpertsQueryEvent
  | SSEChunkChatEvent
  | SSEChunkQueryEvent
  | SSECitationsChatEvent
  | SSECitationsQueryEvent
  | SSECommissioniEvent
  | SSEBalanceEvent
  | SSECompassChatEvent
  | SSECompassQueryEvent
  | SSETopicStatsEvent
  | SSECitationDetailsEvent
  | SSEHQVariantsEvent
  | SSECompleteEvent
  | SSEErrorEvent;
