import { config } from "@/config";

export interface AppSettings {
  [key: string]: any;
}

export async function getSettings(): Promise<AppSettings> {
  const response = await fetch(`${config.api.baseUrl}/settings/`);
  if (!response.ok) {
    throw new Error(`Failed to fetch settings: ${response.statusText}`);
  }
  return response.json();
}

export async function updateSettings(settings: AppSettings): Promise<AppSettings> {
  const response = await fetch(`${config.api.baseUrl}/settings/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(settings),
  });

  if (!response.ok) {
    throw new Error(`Failed to update settings: ${response.statusText}`);
  }
  return response.json();
}
