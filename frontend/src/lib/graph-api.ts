
import { config } from "@/config";

const WRITE_KEYWORDS = [
  "CREATE", "DELETE", "DETACH", "SET ", "REMOVE", "MERGE",
  "DROP", "FOREACH", "LOAD CSV",
];

/**
 * Check if a Cypher query contains write operations.
 * Used for client-side validation before sending to the backend.
 */
export function isWriteQuery(cypher: string): boolean {
  const upper = cypher.toUpperCase();
  return WRITE_KEYWORDS.some((kw) => upper.includes(kw));
}

export async function getGraphSchema() {
  const response = await fetch(`${config.api.baseUrl}/graph/schema`);
  if (!response.ok) throw new Error("Failed to fetch schema");
  return response.json();
}

export async function getGraphStats() {
    const response = await fetch(`${config.api.baseUrl}/graph/stats`);
    if (!response.ok) throw new Error("Failed to fetch stats");
    return response.json();
}

export async function executeCypherQuery(cypher: string) {
  if (isWriteQuery(cypher)) {
    throw new Error("Operazione di scrittura non consentita. Il Graph Explorer è in modalità sola lettura.");
  }

  const response = await fetch(`${config.api.baseUrl}/graph/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cypher }),
  });
  if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || "Query failed");
  }
  const data = await response.json();
  return data.records || [];
}
