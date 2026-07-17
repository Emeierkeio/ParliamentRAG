/**
 * TypeScript interfaces for the Debate Transcript Viewer feature.
 * These mirror the backend Pydantic models in backend/app/models/transcript.py
 */

export interface TranscriptSpeechRow {
  speech_id: string;
  phase_id: string;
  phase_title: string;
  speaker_id: string;
  first_name: string;
  last_name: string;
  party: string | null;
  speaking_role: string | null;
  is_government_member: boolean;
}

export interface TranscriptResponse {
  debate_id: string;
  debate_title: string;
  session_date: string;
  session_id: string;
  chamber: string;
  speeches: TranscriptSpeechRow[];
}

export interface SpeechTextResponse {
  speech_id: string;
  text: string;
}

export interface SuggestionsResponse {
  questions: string[];
}

export interface SearchMatch {
  speech_id: string;
  snippet: string;
}

export interface TranscriptSearchResponse {
  query: string;
  matches: SearchMatch[];
}

/** Chat message for the transcript chatbot (session-only, no persistence). */
export interface TranscriptMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: TranscriptCitation[];
}

/** Citation from the debate chatbot pointing to a specific speech. */
export interface TranscriptCitation {
  index: number;         // [1], [2], etc.
  speech_id: string;
  speaker_name: string;
  party: string | null;
  chunk_text: string;    // relevant excerpt
}
