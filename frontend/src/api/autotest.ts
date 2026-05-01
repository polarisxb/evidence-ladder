import { request } from "./client";
import type {
  AutoTestDraft,
  AutoTestPlan,
  AutoTestPlanRequest,
  AutoTestRetestDraft,
  AutoTestSummary,
} from "../types";

export async function createAutoTestPlan(body: AutoTestPlanRequest): Promise<AutoTestPlan> {
  const res = await request<{ data: { plan: AutoTestPlan } }>("/autotest/plan", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.data.plan;
}

export async function createAutoTestDraft(body: AutoTestPlanRequest): Promise<AutoTestDraft> {
  const res = await request<{ data: AutoTestDraft }>("/autotest/draft", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.data;
}

export async function getAutoTestSummary(scanId: string): Promise<AutoTestSummary> {
  const res = await request<{ data: AutoTestSummary }>(`/autotest/scans/${scanId}/summary`);
  return res.data;
}

export async function createAutoTestRetestDraft(scanId: string): Promise<AutoTestRetestDraft> {
  const res = await request<{ data: AutoTestRetestDraft }>(
    `/autotest/scans/${scanId}/retest-draft`,
    { method: "POST" },
  );
  return res.data;
}
