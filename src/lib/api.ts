import { config } from "@/config";

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
    max_component_contribution: number;
  };
  generation: {
    models: Record<string, string>;
    position_brief: {
      enabled: boolean;
      max_chunks: number;
      chars_per_chunk: number;
      context_chars: number;
    };
    no_evidence_message: string;
  };
}

export async function getConfig(): Promise<SystemConfig> {
  const response = await fetch(`${config.api.baseUrl}/config`);
  if (!response.ok) {
    throw new Error(`Errore nel caricamento config: ${response.statusText}`);
  }
  const raw = await response.json();

  // Return only the editable and functionally active settings.
  // - compass, coalitions, citation, all_parties: read-only, not editable via PUT
  // - generation.parameters: hardcoded in backend services, not read from config
  // - generation.require_all_parties: not used by any backend service
  // - authority.normalization: always "percentile", never read from config
  return {
    retrieval: raw.retrieval,
    authority: {
      weights: raw.authority.weights,
      time_decay_acts_half_life: raw.authority.time_decay_acts_half_life,
      time_decay_speeches_half_life: raw.authority.time_decay_speeches_half_life,
      max_component_contribution: raw.authority.max_component_contribution,
    },
    generation: {
      models: raw.generation.models,
      position_brief: raw.generation.position_brief,
      no_evidence_message: raw.generation.no_evidence_message,
    },
  };
}

export interface ConfigUpdate {
  retrieval?: Partial<SystemConfig["retrieval"]>;
  authority?: Partial<SystemConfig["authority"]>;
  generation?: Partial<SystemConfig["generation"]>;
}

export async function reloadConfig(): Promise<SystemConfig> {
  const response = await fetch(`${config.api.baseUrl}/config/reload`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Errore nel reload config: ${response.statusText}`);
  }
  const raw = await response.json();
  return {
    retrieval: raw.retrieval,
    authority: {
      weights: raw.authority.weights,
      time_decay_acts_half_life: raw.authority.time_decay_acts_half_life,
      time_decay_speeches_half_life: raw.authority.time_decay_speeches_half_life,
      max_component_contribution: raw.authority.max_component_contribution,
    },
    generation: {
      models: raw.generation.models,
      position_brief: raw.generation.position_brief,
      no_evidence_message: raw.generation.no_evidence_message,
    },
  };
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
  const raw = await response.json();
  return {
    retrieval: raw.retrieval,
    authority: {
      weights: raw.authority.weights,
      time_decay_acts_half_life: raw.authority.time_decay_acts_half_life,
      time_decay_speeches_half_life: raw.authority.time_decay_speeches_half_life,
      max_component_contribution: raw.authority.max_component_contribution,
    },
    generation: {
      models: raw.generation.models,
      position_brief: raw.generation.position_brief,
      no_evidence_message: raw.generation.no_evidence_message,
    },
  };
}
