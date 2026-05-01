import { request } from "./client";
import type { AttackCase, AttackCaseDetail } from "../types";

export async function getScanCases(scanId: string): Promise<AttackCase[]> {
  const res = await request<{ data: AttackCase[] }>(`/scans/${scanId}/cases`);
  return res.data;
}

export async function getCaseDetail(caseId: string): Promise<AttackCaseDetail> {
  const res = await request<{ data: AttackCaseDetail }>(`/cases/${caseId}`);
  return res.data;
}
