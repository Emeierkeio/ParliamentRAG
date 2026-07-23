import { config } from "@/config";

// Config API — maps to GET/PUT /api/config
export interface SystemConfig {
  retrieval: {
    dense_similarity_threshold: number;
    graph_semantic_threshold: number;
    graph_chunk_similarity_threshold: number;
    graph_max_acts_per_query: number;
    rrf_k: number;
    rrf_weights: Record<string, number>;
  };
  authority: {
    weights: Record<string, number>;
    time_decay_acts_half_life: number;
    time_decay_speeches_half_life: number;
    acts_relevance_threshold: number;
    interventions_relevance_threshold: number;
    max_component_contribution: number;
  };
  generation: {
    models: Record<string, string>;
  };
  query_rewriting: {
    enabled: boolean;
    model: string;
    max_query_words: number;
  };
}

function mapRawToConfig(raw: unknown): SystemConfig {
  const r = raw as Record<string, Record<string, unknown>>;
  const retrieval = r.retrieval as SystemConfig["retrieval"] & Record<string, unknown>;
  const authority = r.authority as SystemConfig["authority"] & Record<string, unknown>;
  const generation = r.generation as SystemConfig["generation"] & Record<string, unknown>;
  return {
    retrieval: {
      dense_similarity_threshold: retrieval.dense_similarity_threshold,
      graph_semantic_threshold: retrieval.graph_semantic_threshold,
      graph_chunk_similarity_threshold: (retrieval.graph_chunk_similarity_threshold as number | undefined) ?? 0.3,
      graph_max_acts_per_query: (retrieval.graph_max_acts_per_query as number | undefined) ?? 100,
      rrf_k: (retrieval.rrf_k as number | undefined) ?? 60,
      rrf_weights: (retrieval.rrf_weights as Record<string, number> | undefined) ?? { dense: 1.0, sparse: 0.8, graph: 0.5, ner: 0.9 },
    },
    authority: {
      weights: authority.weights as Record<string, number>,
      time_decay_acts_half_life: authority.time_decay_acts_half_life,
      time_decay_speeches_half_life: authority.time_decay_speeches_half_life,
      acts_relevance_threshold: (authority.acts_relevance_threshold as number | undefined) ?? 0.25,
      interventions_relevance_threshold: (authority.interventions_relevance_threshold as number | undefined) ?? 0.25,
      max_component_contribution: authority.max_component_contribution,
    },
    generation: {
      models: generation.models as Record<string, string>,
    },
    query_rewriting: (r.query_rewriting as SystemConfig["query_rewriting"] | undefined) ?? { enabled: true, model: "gpt-4o-mini", max_query_words: 5 },
  };
}

export async function getConfig(): Promise<SystemConfig> {
  const response = await fetch(`${config.api.baseUrl}/config`);
  if (!response.ok) {
    throw new Error(`Failed to load config: ${response.statusText}`);
  }
  return mapRawToConfig(await response.json());
}

export interface ConfigUpdate {
  retrieval?: Partial<SystemConfig["retrieval"]>;
  authority?: Partial<SystemConfig["authority"]>;
  generation?: Partial<SystemConfig["generation"]>;
  query_rewriting?: Partial<SystemConfig["query_rewriting"]>;
}

export async function reloadConfig(): Promise<SystemConfig> {
  const response = await fetch(`${config.api.baseUrl}/config/reload`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Errore nel reload config: ${response.statusText}`);
  }
  return mapRawToConfig(await response.json());
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
  return mapRawToConfig(await response.json());
}
