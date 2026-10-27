import type { ScanTask } from "../types";

/** The `t` returned by useLocale(). */
export type Translate = (key: string, vars?: Record<string, string | number>) => string;

/**
 * Display text for an internal id (`labels.<group>.<id>` in the locale files).
 * The API speaks in ids such as `prompt_injection`, `run_canary_retest` or
 * `openai_compatible`; pages show them through these helpers so no raw id or
 * hard-coded English reaches the UI. Unknown ids fall back to `fallback`
 * (usually the server's own name) or to the id with spaces.
 */
function lookup(t: Translate, group: string, id: string | null | undefined, fallback?: string | null): string {
  if (!id) return fallback || "—";
  const key = `labels.${group}.${id}`;
  const text = t(key);
  return text !== key ? text : fallback || id.replace(/_/g, " ");
}

export const categoryLabel = (t: Translate, id: string | null | undefined, fallback?: string | null) =>
  lookup(t, "category", id, fallback);

export function categoryDescription(t: Translate, id: string, fallback?: string | null): string {
  const key = `labels.categoryDesc.${id}`;
  const text = t(key);
  return text !== key ? text : fallback ?? "";
}

export const scanStatusLabel = (t: Translate, status: string | null | undefined) => lookup(t, "scanStatus", status);
export const targetTypeLabel = (t: Translate, type: string | null | undefined) => lookup(t, "targetType", type);
export const riskLevelLabel = (t: Translate, level: string | null | undefined) => lookup(t, "risk", level);
export const healthLabel = (t: Translate, health: string | null | undefined) => lookup(t, "health", health);
export const retestActionLabel = (t: Translate, action: string) => lookup(t, "retestAction", action);
export const phaseLabel = (t: Translate, phase: string) => lookup(t, "phase", phase);
export const strategyLabel = (t: Translate, strategy: string) => lookup(t, "strategy", strategy);
export const owaspItemLabel = (t: Translate, id: string, fallback?: string | null) => lookup(t, "owasp", id, fallback);
export const probeStateLabel = (t: Translate, state: string) => lookup(t, "probeState", state);

export function builtinLevelLabel(t: Translate, level: number): { name: string; desc: string } {
  return {
    name: lookup(t, "builtinLevel", String(level), `Level ${level}`),
    desc: lookup(t, "builtinLevelDesc", String(level), ""),
  };
}

// Backend health messages (scan_runner / response_screening) are fixed English
// templates; recognized ones are shown in the reader's language, anything else
// verbatim. Keep these patterns in step with the backend wording.
const HEALTH_REASONS: Array<[RegExp, string, (m: RegExpMatchArray) => Record<string, string>]> = [
  [/^Health probe detected repeated non-evaluable benign responses\.\s*(.*)$/s, "probeRepeated", (m) => ({ detail: m[1] })],
  [/^Health probe detected (\d+)\/(\d+) non-evaluable benign responses\.\s*(.*)$/s, "probeRatio",
    (m) => ({ n: m[1], total: m[2], detail: m[3] })],
  [/^Target emitted (\d+) consecutive non-evaluable responses \((.+)\); dead-man switch tripped\.$/s, "deadMan",
    (m) => ({ n: m[1], signature: m[2] })],
  [/^Repeated non-evaluable signature during scan: (.+) \((\d+) consecutive responses\)\.$/s, "signatureStreak",
    (m) => ({ signature: m[1], n: m[2] })],
  [/^High non-evaluable ratio during scan: (\d+)\/(\d+) recent responses\.$/s, "invalidRatio",
    (m) => ({ n: m[1], total: m[2] })],
];

const NOT_EVALUABLE_DETAILS: Record<string, string> = {
  "The response matched a known non-model fallback template.": "known_fallback",
  "The response matched a target-configured non-model response rule.": "configured_origin_rule",
  "The request failed before a stable model response could be evaluated.": "transport_error",
  "The endpoint returned a non-success HTTP status instead of a stable model response.": "http_error",
  "The adapter reported a failure instead of returning a stable model response.": "adapter_error",
  "The adapter response could not be extracted into a stable model reply.": "extract_error",
  "The endpoint returned an HTML or gateway error page instead of model output.": "html_error",
  "The endpoint returned an empty response, so there is no model output to evaluate.": "empty_response",
  "The target returned an execution error instead of model output.": "execution_error",
  "The target system explicitly reported that the request did not reach the LLM.": "blocked_by_target",
  "The response could not be treated as stable model output.": "default",
};

function localizeNotEvaluableDetail(t: Translate, detail: string): string {
  const m = detail.match(/^(.*?)(?:\s*Matched signature: (.+)\.)?$/s);
  const code = NOT_EVALUABLE_DETAILS[(m?.[1] ?? detail).trim()];
  if (!code) return detail;
  const base = lookup(t, "notEvaluableReason", code, detail);
  return m?.[2] ? `${base} ${t("labels.notEvaluableReason.matchedSignature", { signature: m[2] })}` : base;
}

/** A backend target-health reason in the reader's language (unknown text passes through). */
export function localizeHealthReason(t: Translate, reason: string | null | undefined): string | null {
  if (!reason) return reason ?? null;
  for (const [pattern, code, vars] of HEALTH_REASONS) {
    const m = reason.match(pattern);
    if (!m) continue;
    const params = vars(m);
    if (params.detail) params.detail = localizeNotEvaluableDetail(t, params.detail);
    const key = `labels.healthReason.${code}`;
    const text = t(key, params);
    return text !== key ? text.trim() : reason;
  }
  return reason;
}

/** A pending/running scan younger than this may simply not have reached its runner yet. */
export const INTERRUPT_GRACE_MS = 60_000;

/**
 * True when the backend says no runner is executing this pending/running scan,
 * e.g. after a restart: it will never finish on its own.
 */
export function isInterruptedScan(
  scan: Pick<ScanTask, "status" | "created_at"> & { runner_active?: boolean | null },
  now: number = Date.now(),
): boolean {
  if (scan.status !== "pending" && scan.status !== "running") return false;
  if (scan.runner_active !== false) return false;
  return now - new Date(scan.created_at).getTime() > INTERRUPT_GRACE_MS;
}
