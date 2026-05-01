import { request, API_BASE, download } from "./client";
import type { SecurityReport, AttackResult } from "../types";

export async function getReport(scanId: string): Promise<SecurityReport> {
  const res = await request<{ data: SecurityReport }>(`/reports/${scanId}`);
  return res.data;
}

export async function getAttackResults(
  scanId: string,
  category?: string,
  successfulOnly = false,
): Promise<AttackResult[]> {
  let url = `/reports/${scanId}/results?`;
  if (category) url += `category=${category}&`;
  if (successfulOnly) url += `successful_only=true`;
  const res = await request<{ data: AttackResult[] }>(url);
  return res.data;
}

export async function reviewAttackResult(
  resultId: string,
  verdictStatus: "manual_verified" | "false_positive" | "reset",
  reviewNote?: string,
): Promise<AttackResult> {
  const res = await request<{ data: AttackResult }>(`/reports/results/${resultId}/review`, {
    method: "POST",
    body: JSON.stringify({
      verdict_status: verdictStatus,
      review_note: reviewNote ?? null,
    }),
  });
  return res.data;
}

export function getExportUrl(scanId: string, format: "json" | "html"): string {
  return `${API_BASE}/reports/${scanId}/export/${format}`;
}

export async function downloadReport(scanId: string, format: "json" | "html"): Promise<void> {
  await download(`/reports/${scanId}/export/${format}`);
}
