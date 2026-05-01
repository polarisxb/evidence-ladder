import { request } from "./client";

export interface AppSettings {
  openai_api_key_set: boolean;
  openai_base_url: string | null;
  openai_model: string;
  openai_mini_model: string;
  database_url: string;
  cors_origins?: string[];
  allow_localhost_targets?: boolean;
  debug: boolean;
}

export async function getSettings(): Promise<AppSettings> {
  const res = await request<{ data: AppSettings }>("/settings");
  return res.data;
}
