import { useState } from "react";
import type { ResponseEvaluation } from "../types";
import { humanizeResponseEvaluationToken } from "../utils/responseEvaluation";

interface ResponseEvaluationPanelProps {
  evaluation?: ResponseEvaluation | null;
  t?: (key: string) => string;
}

type ProvenanceStatus = "model" | "post_processed" | "blocked" | "uncertain";

function resolveProvenanceStatus(evaluation: ResponseEvaluation): ProvenanceStatus {
  if (evaluation.model_invoked === false) return "blocked";
  if (evaluation.model_invoked === true && evaluation.post_processed === true) return "post_processed";
  if (evaluation.model_invoked === true) return "model";
  // Fallback: derive from legacy response_origin
  const origin = evaluation.response_origin;
  if (origin === "model") return "model";
  if (origin === "app_fallback") return "blocked";
  if (origin === "transport_error" || origin === "adapter_error" || origin === "gateway_error") return "blocked";
  return "uncertain";
}

const STATUS_CONFIG: Record<ProvenanceStatus, { icon: string; borderColor: string; bgColor: string; q1Key: string; q2Key: string }> = {
  model:          { icon: "🧠", borderColor: "border-emerald-200", bgColor: "bg-emerald-50/60", q1Key: "results.provenanceModelInvokedTrue",  q2Key: "results.provenancePostProcessedFalse" },
  post_processed: { icon: "✏️", borderColor: "border-amber-200",   bgColor: "bg-amber-50/60",   q1Key: "results.provenanceModelInvokedTrue",  q2Key: "results.provenancePostProcessedTrue" },
  blocked:        { icon: "🛡️", borderColor: "border-blue-200",    bgColor: "bg-blue-50/60",    q1Key: "results.provenanceModelInvokedFalse", q2Key: "" },
  uncertain:      { icon: "❓", borderColor: "border-slate-200",   bgColor: "bg-slate-50/60",   q1Key: "results.provenanceUnknown",           q2Key: "" },
};

export function ResponseEvaluationPanel({ evaluation, t }: ResponseEvaluationPanelProps) {
  const _t = t ?? ((key: string) => key);
  const [expanded, setExpanded] = useState(false);
  if (!evaluation) return null;

  const status = resolveProvenanceStatus(evaluation);
  const cfg = STATUS_CONFIG[status];

  return (
    <div className={`rounded-lg border ${cfg.borderColor} ${cfg.bgColor} p-3 space-y-2`}>
      <p className="text-xs uppercase tracking-wide font-semibold text-slate-600">{_t("results.responseProvenance")}</p>

      {/* Primary two-question display */}
      <div className="space-y-1">
        <div className="flex items-start gap-2">
          <span className="text-base leading-5">{cfg.icon}</span>
          <span className="text-sm font-medium text-slate-900">{_t(cfg.q1Key)}</span>
        </div>
        {cfg.q2Key && (
          <div className="flex items-start gap-2 ml-6">
            <span className="text-xs text-slate-600">
              {status === "post_processed" ? "✏️" : "✅"} {_t(cfg.q2Key)}
            </span>
          </div>
        )}
        {evaluation.block_reason && status === "blocked" && (
          <div className="flex items-start gap-2 ml-6">
            <span className="text-xs text-slate-600">
              {_t(`results.blockReason.${evaluation.block_reason}`) !== `results.blockReason.${evaluation.block_reason}`
                ? _t(`results.blockReason.${evaluation.block_reason}`)
                : humanizeResponseEvaluationToken(evaluation.block_reason)}
            </span>
          </div>
        )}
        {evaluation.post_reason && status === "post_processed" && (
          <div className="flex items-start gap-2 ml-6">
            <span className="text-xs text-slate-600">
              {_t(`results.postReason.${evaluation.post_reason}`) !== `results.postReason.${evaluation.post_reason}`
                ? _t(`results.postReason.${evaluation.post_reason}`)
                : humanizeResponseEvaluationToken(evaluation.post_reason)}
            </span>
          </div>
        )}
        {status === "uncertain" && (
          <p className="text-xs text-slate-500 ml-6">{_t("results.provenanceUnknownHint")}</p>
        )}
      </div>

      {/* Provenance source badge + confidence */}
      <div className="flex items-center gap-2 flex-wrap">
        {evaluation.provenance_source && (
          <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200">
            {_t("results.provenanceSourceLabel")}: {_t(`results.provenanceSource.${evaluation.provenance_source}`) !== `results.provenanceSource.${evaluation.provenance_source}`
              ? _t(`results.provenanceSource.${evaluation.provenance_source}`)
              : humanizeResponseEvaluationToken(evaluation.provenance_source)}
          </span>
        )}
        {evaluation.origin_confidence && (
          <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200">
            {humanizeResponseEvaluationToken(evaluation.origin_confidence)}
          </span>
        )}
        {evaluation.evaluation_validity === "not_evaluable" && (
          <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-orange-50 text-orange-900 border border-orange-200">
            {_t("common.notEvaluable")}
          </span>
        )}
      </div>

      {/* Collapsible details */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-slate-500 hover:text-slate-700 cursor-pointer"
      >
        {expanded ? "▾ " + _t("common.collapse") : "▸ " + _t("common.expand")}
      </button>

      {expanded && (
        <div className="rounded-md border border-slate-200 bg-white px-3 py-2 space-y-1 text-xs text-slate-700">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <p>
              <span className="font-semibold text-slate-900">{_t("results.responseOriginLabel")}:</span>{" "}
              {humanizeResponseEvaluationToken(evaluation.response_origin)}
            </p>
            <p>
              <span className="font-semibold text-slate-900">{_t("results.evaluationValidityLabel")}:</span>{" "}
              {evaluation.evaluation_validity === "not_evaluable" ? _t("common.notEvaluable") : _t("common.evaluable")}
            </p>
            {evaluation.invalid_reason && (
              <p>
                <span className="font-semibold text-slate-900">{_t("results.invalidReasonLabel")}:</span>{" "}
                {humanizeResponseEvaluationToken(evaluation.invalid_reason)}
              </p>
            )}
            {evaluation.matched_signature && (
              <p>
                <span className="font-semibold text-slate-900">{_t("results.matchedSignatureLabel")}:</span>{" "}
                <span className="font-mono">{evaluation.matched_signature}</span>
              </p>
            )}
            {evaluation.http_status != null && (
              <p>
                <span className="font-semibold text-slate-900">{_t("results.httpStatusLabel")}:</span>{" "}
                <span className="font-mono">{evaluation.http_status}</span>
              </p>
            )}
            {evaluation.content_type && (
              <p>
                <span className="font-semibold text-slate-900">{_t("results.contentTypeLabel")}:</span>{" "}
                <span className="font-mono">{evaluation.content_type}</span>
              </p>
            )}
            <p>
              <span className="font-semibold text-slate-900">{_t("results.transportLabel")}:</span>{" "}
              {evaluation.transport_ok === false ? "✗" : "✓"}
            </p>
          </div>

          {evaluation.baseline_probe && (
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 space-y-1 mt-1">
              <p className="text-xs font-semibold text-slate-900 flex items-center gap-2">
                {_t("results.baselineProbeLabel")}
                {evaluation.baseline_probe.cached && (
                  <span className="text-[10px] font-normal text-slate-500">
                    ({_t("results.baselineProbeCachedHint")})
                  </span>
                )}
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                {evaluation.baseline_probe.status === "ok" ? (
                  <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-emerald-50 text-emerald-700 border border-emerald-200">
                    {_t("results.baselineProbeOkLabel")}
                  </span>
                ) : evaluation.baseline_probe.status === "failed" ? (
                  <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-rose-50 text-rose-700 border border-rose-200">
                    {_t("results.baselineProbeFailedLabel")}
                  </span>
                ) : null}
                {evaluation.baseline_probe.http_status != null && (
                  <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-slate-50 text-slate-700 border border-slate-200 font-mono">
                    HTTP {evaluation.baseline_probe.http_status}
                  </span>
                )}
              </div>
              {evaluation.baseline_probe.reason && (
                <p className="text-xs text-slate-700">
                  <span className="font-semibold text-slate-900">{_t("results.baselineProbeReasonLabel")}:</span>{" "}
                  <span className="font-mono">{evaluation.baseline_probe.reason}</span>
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
