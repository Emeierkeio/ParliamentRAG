import { config } from "@/config";

/**
 * Query di sola lettura sul knowledge graph via endpoint pubblico esistente
 * (POST /graph/query, campo `cypher`). Il backend blocca le query di
 * scrittura: qui il grafo è infrastruttura, non feature (vedi
 * RADICAL_REDESIGN.md §7). Nessun uso al di fuori delle pagine entità.
 */
export async function graphQuery<T = Record<string, unknown>>(
  cypher: string
): Promise<T[]> {
  const res = await fetch(`${config.api.baseUrl}/graph/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cypher }),
  });
  if (!res.ok) throw new Error(`graph query failed: ${res.status}`);
  const data = await res.json();
  return (data.records ?? []) as T[];
}

/** Id persona camera.it: "http://dati.camera.it/ocd/persona.rdf/p307394" -> "p307394" */
export function deputySlug(uri: string): string {
  return uri.split("/").pop() ?? uri;
}

export function deputyUriFromSlug(slug: string): string {
  return `http://dati.camera.it/ocd/persona.rdf/${slug}`;
}
