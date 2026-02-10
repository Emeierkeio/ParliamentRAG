/**
 * Evaluation API client for ParliamentRAG scientific assessment.
 */

import { config } from "@/config";
import type { EvaluationDashboardData, AutomatedMetrics } from "@/types/evaluation";

const BASE_URL = `${config.api.baseUrl}/evaluation`;

/**
 * Get full dashboard data (automated + human metrics)
 */
export async function getDashboardData(): Promise<EvaluationDashboardData> {
  const response = await fetch(`${BASE_URL}/dashboard`);
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard data: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Get automated metrics for a specific chat
 */
export async function getChatMetrics(chatId: string): Promise<AutomatedMetrics> {
  const response = await fetch(`${BASE_URL}/metrics/${chatId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch chat metrics: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Get CSV export URL
 */
export function getExportCsvUrl(): string {
  return `${BASE_URL}/export/csv`;
}
