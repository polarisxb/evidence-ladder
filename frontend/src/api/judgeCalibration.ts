import { request } from "./client";
import type {
  JudgeCalibrationRun,
  JudgeCalibrationSample,
  JudgeCalibrationSummary,
  JudgeGoldLabel,
} from "../types";

// ── Samples ───────────────────────────────────────────────────────────────────

export interface CreateSampleParams {
  attack_case_id: string;
  source_type: string;
  sampling_reason?: string;
  is_drift_sample?: boolean;
  label_version?: string;
  gold_label?: JudgeGoldLabel;
  gold_rationale?: string;
  labeler?: string;
}

export async function createCalibrationSample(
  params: CreateSampleParams,
): Promise<JudgeCalibrationSample> {
  const res = await request<{ data: JudgeCalibrationSample }>(
    "/judge/calibration/samples",
    { method: "POST", body: JSON.stringify(params) },
  );
  return res.data;
}

export async function listCalibrationSamples(params?: {
  source_type?: string;
  label_version?: string;
  has_gold_label?: boolean;
  is_drift_sample?: boolean;
  limit?: number;
  offset?: number;
}): Promise<{ data: JudgeCalibrationSample[]; count: number }> {
  const qs = new URLSearchParams();
  if (params?.source_type) qs.set("source_type", params.source_type);
  if (params?.label_version) qs.set("label_version", params.label_version);
  if (params?.has_gold_label != null) qs.set("has_gold_label", String(params.has_gold_label));
  if (params?.is_drift_sample != null) qs.set("is_drift_sample", String(params.is_drift_sample));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const res = await request<{ data: JudgeCalibrationSample[]; count: number }>(
    `/judge/calibration/samples${qs.toString() ? `?${qs}` : ""}`,
  );
  return res;
}

export async function updateCalibrationSample(
  sampleId: string,
  patch: {
    gold_label?: JudgeGoldLabel;
    gold_rationale?: string;
    labeler?: string;
    label_version?: string;
    is_drift_sample?: boolean;
  },
): Promise<JudgeCalibrationSample> {
  const res = await request<{ data: JudgeCalibrationSample }>(
    `/judge/calibration/samples/${sampleId}`,
    { method: "PATCH", body: JSON.stringify(patch) },
  );
  return res.data;
}

export async function deleteCalibrationSample(sampleId: string): Promise<void> {
  await request<{ data: { id: string }; message: string }>(
    `/judge/calibration/samples/${sampleId}`,
    { method: "DELETE" },
  );
}

export async function batchDeleteCalibrationSamples(ids: string[]): Promise<number> {
  // POST + body (not DELETE + body) because many HTTP layers strip bodies
  // from DELETE requests.
  const res = await request<{ data: { deleted: number }; message: string }>(
    `/judge/calibration/samples/delete-batch`,
    { method: "POST", body: JSON.stringify({ ids }) },
  );
  return res.data.deleted;
}

export async function deleteAllCalibrationSamples(params?: {
  source_type?: string;
}): Promise<number> {
  const qs = new URLSearchParams();
  if (params?.source_type) qs.set("source_type", params.source_type);
  const res = await request<{ data: { deleted: number }; message: string }>(
    `/judge/calibration/samples${qs.toString() ? `?${qs}` : ""}`,
    { method: "DELETE" },
  );
  return res.data.deleted;
}

export async function batchSampleProduction(params?: {
  limit?: number;
  category?: string;
  business_verification_status?: string;
}): Promise<{ data: JudgeCalibrationSample[]; count: number; message: string }> {
  const qs = new URLSearchParams();
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.category) qs.set("category", params.category);
  if (params?.business_verification_status)
    qs.set("business_verification_status", params.business_verification_status);
  const res = await request<{ data: JudgeCalibrationSample[]; count: number; message: string }>(
    `/judge/calibration/samples/batch${qs.toString() ? `?${qs}` : ""}`,
    { method: "POST" },
  );
  return res;
}

// ── Runs ──────────────────────────────────────────────────────────────────────

export async function createCalibrationRun(params?: {
  name?: string;
  filters_json?: Record<string, unknown>;
}): Promise<JudgeCalibrationRun> {
  const res = await request<{ data: JudgeCalibrationRun }>(
    "/judge/calibration/runs",
    {
      method: "POST",
      body: JSON.stringify({ run_mode: "snapshot_eval", ...params }),
    },
  );
  return res.data;
}

export async function getCalibrationRun(runId: string): Promise<JudgeCalibrationRun> {
  const res = await request<{ data: JudgeCalibrationRun }>(`/judge/calibration/runs/${runId}`);
  return res.data;
}

export async function listCalibrationRuns(params?: {
  limit?: number;
  offset?: number;
}): Promise<{ data: JudgeCalibrationRun[]; count: number }> {
  const qs = new URLSearchParams();
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  const res = await request<{ data: JudgeCalibrationRun[]; count: number }>(
    `/judge/calibration/runs${qs.toString() ? `?${qs}` : ""}`,
  );
  return res;
}

// ── Summary ───────────────────────────────────────────────────────────────────

export async function getCalibrationSummary(params?: {
  label_version?: string;
  source_type?: string;
  category?: string;
  target_type?: string;
  judge_version?: string;
  business_verification_status?: string;
  date_from?: string;
  date_to?: string;
}): Promise<JudgeCalibrationSummary | null> {
  const qs = new URLSearchParams();
  if (params?.label_version) qs.set("label_version", params.label_version);
  if (params?.source_type) qs.set("source_type", params.source_type);
  if (params?.category) qs.set("category", params.category);
  if (params?.target_type) qs.set("target_type", params.target_type);
  if (params?.judge_version) qs.set("judge_version", params.judge_version);
  if (params?.business_verification_status)
    qs.set("business_verification_status", params.business_verification_status);
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  const res = await request<{ data: JudgeCalibrationSummary | null }>(
    `/judge/calibration/summary${qs.toString() ? `?${qs}` : ""}`,
  );
  return res.data;
}
