
import { config } from "@/config";

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
