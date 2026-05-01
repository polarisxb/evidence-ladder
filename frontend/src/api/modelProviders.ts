import { request } from "./client";
import type { ModelProvider, ModelProviderCreate, ModelProviderUpdate } from "../types";

const BASE = "/model-providers";

export async function listModelProviders(): Promise<ModelProvider[]> {
  const res = await request<{ data: ModelProvider[] }>(BASE);
  return res.data;
}

export async function createModelProvider(body: ModelProviderCreate): Promise<ModelProvider> {
  const res = await request<{ data: ModelProvider }>(BASE, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.data;
}

export async function updateModelProvider(
  id: string,
  body: ModelProviderUpdate,
): Promise<ModelProvider> {
  const res = await request<{ data: ModelProvider }>(`${BASE}/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return res.data;
}

export async function deleteModelProvider(id: string): Promise<void> {
  await request(`${BASE}/${id}`, { method: "DELETE" });
}

export async function testModelProvider(
  id: string,
): Promise<{ connected: boolean; model?: string; error?: string }> {
  const res = await request<{ data: { connected: boolean; model?: string; error?: string } }>(
    `${BASE}/${id}/test`,
    { method: "POST" },
  );
  return res.data;
}

export async function setJudgeDefault(id: string): Promise<ModelProvider> {
  const res = await request<{ data: ModelProvider }>(`${BASE}/${id}/set-judge`, {
    method: "POST",
  });
  return res.data;
}

export async function setGenerationDefault(id: string): Promise<ModelProvider> {
  const res = await request<{ data: ModelProvider }>(`${BASE}/${id}/set-generation`, {
    method: "POST",
  });
  return res.data;
}

export async function fetchProviderModels(params: {
  api_key?: string | null;
  base_url?: string | null;
  provider_type?: string;
  provider_id?: string | null;
}): Promise<string[]> {
  const res = await request<{ data: { models: string[]; total: number } }>(
    `${BASE}/fetch-models`,
    {
      method: "POST",
      body: JSON.stringify(params),
    },
  );
  return res.data.models;
}
