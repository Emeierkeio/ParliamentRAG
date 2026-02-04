/**
 * Tipi per le API
 */

import type { Citation, Expert, BalanceMetrics, ProcessingProgress } from "./chat";

// Request types
export interface QueryRequest {
  query: string;
  conversationId?: string;
  options?: QueryOptions;
}

export interface QueryOptions {
  maxCitations?: number;
  maxExperts?: number;
  minBalanceThreshold?: number; // Soglia minima di bilanciamento richiesta
  includedGroups?: string[]; // Filtra per gruppi specifici (opzionale)
}

// Response types
export interface QueryResponse {
  id: string;
  answer: string;
  citations: Citation[];
  experts: Expert[];
  balanceMetrics: BalanceMetrics;
  processingTime: number;
}

// Streaming response events
export type StreamEventType =
  | "progress"
  | "chunk"
  | "citation"
  | "expert"
  | "balance"
  | "complete"
  | "error";

export interface StreamEvent {
  type: StreamEventType;
  data: StreamEventData;
}

export type StreamEventData =
  | ProgressEventData
  | ChunkEventData
  | CitationEventData
  | ExpertEventData
  | BalanceEventData
  | CompleteEventData
  | ErrorEventData;

export interface ProgressEventData {
  progress: ProcessingProgress;
}

export interface ChunkEventData {
  chunk: string;
}

export interface CitationEventData {
  citation: Citation;
}

export interface ExpertEventData {
  expert: Expert;
}

export interface BalanceEventData {
  balanceMetrics: BalanceMetrics;
}

export interface CompleteEventData {
  messageId: string;
  processingTime: number;
}

export interface ErrorEventData {
  code: string;
  message: string;
}

// API Error
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}
