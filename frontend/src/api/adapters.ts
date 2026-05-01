import { request } from "./client";
import type {
  Adapter,
  AdapterConfig,
  AdapterProbeTestResult,
  AdapterTestRequest,
  AdapterTestResult,
  ProbeTestRequest,
} from "../types";

export async function getAdapters(): Promise<Adapter[]> {
  const res = await request<{ data: Adapter[] }>("/adapters");
  return res.data;
}

export async function getAdapter(adapterId: string): Promise<Adapter> {
  const res = await request<{ data: Adapter }>(`/adapters/${adapterId}`);
  return res.data;
}

export async function createAdapter(body: AdapterConfig): Promise<Adapter> {
  const res = await request<{ data: Adapter }>("/adapters", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.data;
}

export async function updateAdapter(adapterId: string, body: Partial<AdapterConfig>): Promise<Adapter> {
  const res = await request<{ data: Adapter }>(`/adapters/${adapterId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return res.data;
}

export async function testAdapter(body: AdapterTestRequest): Promise<AdapterTestResult> {
  const res = await request<{ data: AdapterTestResult }>("/adapters/test", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.data;
}

export async function testAdapterProbe(body: ProbeTestRequest): Promise<AdapterProbeTestResult> {
  const res = await request<{ data: AdapterProbeTestResult }>("/adapters/probe/test", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.data;
}
