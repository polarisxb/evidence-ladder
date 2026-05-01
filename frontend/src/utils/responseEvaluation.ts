import type { BaselineProbeResult, ResponseEvaluation } from "../types";

type ResponseEvaluationLike =
  | { response_evaluation?: ResponseEvaluation | null; analysis_raw?: Record<string, unknown> | null; summary_json?: Record<string, unknown> | null }
  | Record<string, unknown>
  | null
  | undefined;

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string" && entry.trim().length > 0) : [];
}

export function humanizeResponseEvaluationToken(value?: string | null): string {
  if (!value) return "";
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function normalizeBaselineProbe(value: unknown): BaselineProbeResult | null {
  const record = asRecord(value);
  if (!record) return null;
  return {
    status: asString(record.status),
    reason: asString(record.reason),
    http_status: asNumber(record.http_status),
    probed_at: asString(record.probed_at),
    cached: asBoolean(record.cached),
  };
}

function normalizeResponseEvaluation(value: unknown): ResponseEvaluation | null {
  const record = asRecord(value);
  if (!record) return null;
  const responseOrigin = asString(record.response_origin);
  const originConfidence = asString(record.origin_confidence);
  const evaluationValidity = asString(record.evaluation_validity);
  if (!responseOrigin || !originConfidence || !evaluationValidity) return null;
  return {
    response_origin: responseOrigin,
    origin_confidence: originConfidence,
    evaluation_validity: evaluationValidity,
    invalid_reason: asString(record.invalid_reason),
    matched_signature: asString(record.matched_signature),
    transport_ok: asBoolean(record.transport_ok),
    http_status: asNumber(record.http_status),
    content_type: asString(record.content_type),
    evidence_codes: asStringArray(record.evidence_codes),
    baseline_probe: normalizeBaselineProbe(record.baseline_probe),
  };
}

export function resolveResponseEvaluation(source: ResponseEvaluationLike): ResponseEvaluation | null {
  const direct = normalizeResponseEvaluation(asRecord(source)?.response_evaluation ?? source);
  if (direct) return direct;

  const analysisRaw = normalizeResponseEvaluation(asRecord(asRecord(source)?.analysis_raw)?.response_evaluation);
  if (analysisRaw) return analysisRaw;

  const summary = normalizeResponseEvaluation(asRecord(asRecord(source)?.summary_json)?.response_evaluation);
  if (summary) return summary;

  return null;
}

export function isNotEvaluableResponse(source: ResponseEvaluationLike): boolean {
  return resolveResponseEvaluation(source)?.evaluation_validity === "not_evaluable";
}

export type NotEvaluableTone = "amber" | "rose" | "fuchsia" | "slate" | "orange";

export interface NotEvaluableDisplayCategory {
  /** i18n key under ``results.notEvaluableCategory.*`` */
  labelKey: string;
  /** Fallback label if the i18n key is missing */
  fallbackLabel: string;
  tone: NotEvaluableTone;
  /** HTTP status captured from the envelope, ``null`` if none */
  httpStatus: number | null;
  /** Baseline probe verdict after the case failed, ``null`` if not run */
  probeStatus: "ok" | "failed" | null;
  /** Target signature matched when ``invalid_reason === configured_origin_rule`` */
  matchedSignature: string | null;
  /** Raw ``invalid_reason`` value (may be surfaced to operators) */
  invalidReason: string | null;
}

/**
 * Turn a not_evaluable ``ResponseEvaluation`` into a UI-friendly category
 * that is strictly more specific than the generic "无法评测" pill. The
 * rules fold together ``invalid_reason`` / ``http_status`` /
 * ``baseline_probe.status`` so that an operator looking at the results
 * list can tell apart:
 *
 *   - model layer silently refused (A class, defense-like behaviour)
 *   - target service returned a non-2xx + probe says target alive
 *     (B class — but a real attack signal: payload crashed the business)
 *   - target is offline (B class — infrastructure issue, not a scan signal)
 *
 * Returns ``null`` when the evaluation is evaluable OR missing, so
 * callers fall back to the original verdict pill.
 *
 * This util deliberately returns structured data (no concatenated
 * strings) so the calling component can run every piece through its
 * locale's ``t(...)`` resolver.
 */
export function notEvaluableDisplayCategory(
  evaluation: ResponseEvaluation | null | undefined,
): NotEvaluableDisplayCategory | null {
  if (!evaluation || evaluation.evaluation_validity !== "not_evaluable") {
    return null;
  }
  const reason = evaluation.invalid_reason ?? "";
  const http = evaluation.http_status ?? null;
  const rawProbe = evaluation.baseline_probe?.status ?? null;
  const probeStatus: "ok" | "failed" | null =
    rawProbe === "ok" ? "ok" : rawProbe === "failed" ? "failed" : null;
  const matchedSignature = evaluation.matched_signature || null;

  const base = {
    httpStatus: http,
    probeStatus,
    matchedSignature,
    invalidReason: reason || null,
  };

  switch (reason) {
    case "known_fallback":
    case "configured_origin_rule": {
      return {
        labelKey: "results.notEvaluableCategory.modelFallback",
        fallbackLabel: "模型回退",
        tone: "amber",
        ...base,
      };
    }
    case "empty_response": {
      if (http !== null && http >= 200 && http < 300) {
        return {
          labelKey: "results.notEvaluableCategory.modelSilentHealthy",
          fallbackLabel: "模型空响应·目标健康",
          tone: "amber",
          ...base,
        };
      }
      return {
        labelKey: "results.notEvaluableCategory.emptyUnknown",
        fallbackLabel: "空响应",
        tone: "slate",
        ...base,
      };
    }
    case "html_error": {
      return {
        labelKey: "results.notEvaluableCategory.gatewayError",
        fallbackLabel: "网关错误",
        tone: "rose",
        ...base,
      };
    }
    case "http_error": {
      return {
        labelKey: "results.notEvaluableCategory.httpError",
        fallbackLabel: "HTTP 错误",
        tone: "rose",
        ...base,
      };
    }
    case "transport_error":
    case "execution_error": {
      return {
        labelKey: "results.notEvaluableCategory.transportError",
        fallbackLabel: "通信异常",
        tone: "rose",
        ...base,
      };
    }
    case "adapter_error":
    case "extract_error": {
      return {
        labelKey: "results.notEvaluableCategory.adapterError",
        fallbackLabel: "适配器异常",
        tone: "fuchsia",
        ...base,
      };
    }
    default: {
      return {
        labelKey: "results.notEvaluableCategory.generic",
        fallbackLabel: "无法评测",
        tone: "orange",
        ...base,
      };
    }
  }
}

const NOT_EVALUABLE_TONE_CLASS: Record<NotEvaluableTone, string> = {
  amber: "bg-amber-50 text-amber-800 border border-amber-200",
  rose: "bg-rose-50 text-rose-700 border border-rose-200",
  fuchsia: "bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200",
  slate: "bg-slate-100 text-slate-700 border border-slate-200",
  orange: "bg-orange-50 text-orange-800 border border-orange-200",
};

export function notEvaluableToneClasses(tone: NotEvaluableTone): string {
  return NOT_EVALUABLE_TONE_CLASS[tone];
}
