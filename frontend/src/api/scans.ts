import { request } from "./client";
import type { ScanConfig, ScanTask } from "../types";

function sanitizeScanConfig(config: ScanConfig): ScanConfig {
  const targetConfig = { ...(config.target_config ?? {}) } as Record<string, unknown>;
  const originRules =
    targetConfig.origin_rules && typeof targetConfig.origin_rules === "object"
      ? { ...(targetConfig.origin_rules as Record<string, unknown>) }
      : null;

  if (originRules) {
    for (const key of Object.keys(originRules)) {
      const value = originRules[key];
      if (value == null || value === "" || (Array.isArray(value) && value.length === 0)) {
        delete originRules[key];
      }
    }
    if (Object.keys(originRules).length > 0) {
      targetConfig.origin_rules = originRules;
    } else {
      delete targetConfig.origin_rules;
    }
  }

  for (const key of Object.keys(targetConfig)) {
    const value = targetConfig[key];
    if (value == null || value === "" || (Array.isArray(value) && value.length === 0)) {
      delete targetConfig[key];
    }
  }

  if (config.target_type !== "builtin_vulnerable") {
    delete targetConfig.vulnerable_level;
  }

  return {
    ...config,
    adapter_id: config.target_type === "adapter" ? config.adapter_id ?? null : undefined,
    target_config: Object.keys(targetConfig).length > 0 ? targetConfig : undefined,
    runtime_vars:
      config.target_type === "adapter"
        ? (config.runtime_vars ?? {})
        : undefined,
  };
}

export async function createScan(config: ScanConfig): Promise<{ task_id: string }> {
  const res = await request<{ data: { task_id: string } }>("/scans", {
    method: "POST",
    body: JSON.stringify(sanitizeScanConfig(config)),
  });
  return res.data;
}

export async function listScans(
  page = 1,
  pageSize = 20,
  status?: string,
  q?: string,
): Promise<{ data: ScanTask[]; total: number }> {
  let url = `/scans?page=${page}&page_size=${pageSize}`;
  if (status) url += `&status=${status}`;
  if (q) url += `&q=${encodeURIComponent(q)}`;
  return request(url);
}

export async function getScan(taskId: string): Promise<ScanTask> {
  const res = await request<{ data: ScanTask }>(`/scans/${taskId}`);
  return res.data;
}

export async function cancelScan(taskId: string): Promise<void> {
  await request(`/scans/${taskId}/cancel`, { method: "POST" });
}

/** Stop a running scan early and finalize a report from saved results. */
export async function finalizeStuckScan(
  taskId: string,
): Promise<{ overall_score: number; status: string; completed_attacks: number }> {
  type FinalizeRes = {
    data: { overall_score: number; status: string; completed_attacks: number };
  };
  const paths = [
    `/scans/${taskId}/pause`,
    `/scans/${taskId}/finalize-stuck`,
    `/reports/${taskId}/finalize-stuck`,
  ];
  let lastErr: Error | undefined;
  for (const path of paths) {
    try {
      const res = await request<FinalizeRes>(path, { method: "POST" });
      return res.data;
    } catch (e) {
      lastErr = e instanceof Error ? e : new Error(String(e));
      const msg = lastErr.message;
      const is404 =
        msg.includes("404") || msg.includes("Not Found") || msg.includes('"detail":"Not Found"');
      if (!is404 || path === paths[paths.length - 1]) {
        throw lastErr;
      }
    }
  }
  throw lastErr ?? new Error("Finalize failed");
}

export async function deleteScan(taskId: string): Promise<void> {
  await request(`/scans/${taskId}`, { method: "DELETE" });
}

export async function retryScan(taskId: string): Promise<{ task_id: string }> {
  const res = await request<{ data: { task_id: string } }>(`/scans/${taskId}/retry`, {
    method: "POST",
  });
  return res.data;
}
