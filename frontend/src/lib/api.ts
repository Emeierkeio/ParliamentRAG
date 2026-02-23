import { config } from "@/config";

export interface AppSettings {
  [key: string]: any;
}

// Legacy settings API (kept for backward compatibility)
export async function getSettings(): Promise<AppSettings> {
  return getConfig();
}

export async function updateSettings(settings: AppSettings): Promise<AppSettings> {
  return updateConfig(settings);
}

// Config API — maps to GET/PUT /api/config
export interface SystemConfig {
  retrieval: {
    dense_top_k: number;
    dense_similarity_threshold: number;
    graph_lexical_min_match: number;
    graph_semantic_threshold: number;
    merger_weights: Record<string, number>;
  };
  authority: {
    weights: Record<string, number>;
    time_decay_acts_half_life: number;
    time_decay_speeches_half_life: number;
    normalization: string;
    max_component_contribution: number;
  };
  compass: {
    purpose: string;
    anchor_groups: Record<string, string[]>;
    ambiguous_groups: Record<string, any>;
    unclassified_groups: string[];
  };
  generation: {
    models: Record<string, string>;
    parameters: {
      max_tokens: number;
      temperature: number;
      top_p: number;
    };
    position_brief: {
      enabled: boolean;
      max_chunks: number;
      chars_per_chunk: number;
      context_chars: number;
    };
    require_all_parties: boolean;
    no_evidence_message: string;
  };
  coalitions: {
    maggioranza: string[];
    opposizione: string[];
  };
  citation: {
    method: string;
    format: string;
    verify_on_insert: boolean;
  };
  all_parties: string[];
}

export async function getConfig(): Promise<SystemConfig> {
  const response = await fetch(`${config.api.baseUrl}/config`);
  if (!response.ok) {
    throw new Error(`Errore nel caricamento config: ${response.statusText}`);
  }
  return response.json();
}

export interface ConfigUpdate {
  retrieval?: Partial<SystemConfig["retrieval"]>;
  authority?: Partial<SystemConfig["authority"]>;
  generation?: Partial<SystemConfig["generation"]>;
}

export async function updateConfig(update: ConfigUpdate): Promise<SystemConfig> {
  const response = await fetch(`${config.api.baseUrl}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Errore nel salvataggio: ${text}`);
  }
  return response.json();
}
