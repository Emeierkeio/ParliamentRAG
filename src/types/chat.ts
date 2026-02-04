/**
 * Tipi per il sistema di chat
 */

export type MessageRole = "user" | "assistant" | "system";

export type MessageStatus = "sending" | "streaming" | "complete" | "error";

export interface Citation {
  chunk_id: string;
  deputato_nome: string;
  deputato_cognome: string;
  gruppo: string;
  coalizione: string;
  testo?: string; // Optional because backend might send quote_text
  quote_text?: string; // Backend field
  full_text?: string;
  data: string;
  similarity: number;
  dibattito?: string;
  debate_id?: string;
  dibattito_id?: string;
  intervention_id?: string;
  intervento_id?: string;
  scheda_camera?: string;
  [key: string]: any; // Allow loose props for now
}

export interface Expert {
  id: string;
  nome: string;
  cognome: string;
  gruppo: string;
  scheda_camera?: string;
  professione?: string;
  istruzione?: string;
  commissione?: string;
  ruolo_istituzionale?: string;
  coalizione: string;
  authority_score: number;
  score_breakdown?: {
    interventi: number;
    atti: number;
    commissione: number;
    professione: number;
    istruzione: number;
    ruolo: number;
  };
  n_interventi_rilevanti: number;
  atti_dettaglio?: Array<{
    titolo: string;
    eurovoc: string;
    is_primo: boolean;
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
