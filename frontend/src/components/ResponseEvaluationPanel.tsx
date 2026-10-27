import { useState } from "react";
import { CheckCircle2, HelpCircle, PenLine, ShieldAlert, type LucideIcon } from "lucide-react";
import type { ResponseEvaluation } from "../types";
import { humanizeResponseEvaluationToken } from "../utils/responseEvaluation";
import type { Translate } from "../utils/labels";

interface ResponseEvaluationPanelProps {
  evaluation?: ResponseEvaluation | null;
  t?: Translate;
  /** "card": a boxed panel of its own; "inline": one line inside another section. */
  variant?: "card" | "inline";
}

type ProvenanceStatus = "model" | "post_processed" | "blocked" | "uncertain";

function resolveProvenanceStatus(evaluation: ResponseEvaluation): ProvenanceStatus {
  if (evaluation.model_invoked === false) return "blocked";
  if (evaluation.model_invoked === true && evaluation.post_processed === true) return "post_processed";
  if (evaluation.model_invoked === true) return "model";
  // Fallback: derive from response_origin
  const origin = evaluation.response_origin;
  if (origin === "model") return "model";
  if (origin === "app_fallback") return "blocked";
  if (origin === "transport_error" || origin === "adapter_error" || origin === "gateway_error") return "blocked";
  return "uncertain";
}

const STATUS_CONFIG: Record<ProvenanceStatus, {
  Icon: LucideIcon; iconClass: string; borderColor: string; bgColor: string; q1Key: string; q2Key: string;
}> = {
  model:          { Icon: CheckCircle2, iconClass: "text-emerald-600", borderColor: "border-emerald-200", bgColor: "bg-emerald-50/60", q1Key: "results.provenanceModelInvokedTrue",  q2Key: "results.provenancePostProcessedFalse" },
  post_processed: { Icon: PenLine,      iconClass: "text-amber-600",   borderColor: "border-amber-200",   bgColor: "bg-amber-50/60",   q1Key: "results.provenanceModelInvokedTrue",  q2Key: "results.provenancePostProcessedTrue" },
  blocked:        { Icon: ShieldAlert,  iconClass: "text-blue-600",    borderColor: "border-blue-200",    bgColor: "bg-blue-50/60",    q1Key: "results.provenanceModelInvokedFalse", q2Key: "" },
  uncertain:      { Icon: HelpCircle,   iconClass: "text-slate-500",   borderColor: "border-slate-200",   bgColor: "bg-slate-50/60",   q1Key: "results.provenanceUnknown",           q2Key: "" },
};

const CHIP = "inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200";

/** `prefix.value` from the locale, or the value made readable when there is no entry. */
function translated(t: Translate, prefix: string, value?: string | null): string {
  if (!value) return "";
  const key = `${prefix}.${value}`;
  const text = t(key);
  return text !== key ? text : humanizeResponseEvaluationToken(value);
}

/** Why the request was blocked or the reply rewritten, when the target said so. */
function reasonText(evaluation: ResponseEvaluation, status: ProvenanceStatus, t: Translate): string {
  if (status === "blocked" && evaluation.block_reason) return translated(t, "results.blockReason", evaluation.block_reason);
  if (status === "post_processed" && evaluation.post_reason) return translated(t, "results.postReason", evaluation.post_reason);
  return "";
}

function Chips({ evaluation, t }: { evaluation: ResponseEvaluation; t: Translate }) {
  return (
    <>
      {evaluation.provenance_source && (
        <span className={CHIP}>
          {t("results.provenanceSourceLabel")}: {translated(t, "results.provenanceSource", evaluation.provenance_source)}
        </span>
      )}
      {evaluation.origin_confidence && (
        <span className={CHIP}>{translated(t, "labels.originConfidence", evaluation.origin_confidence)}</span>
      )}
      {evaluation.evaluation_validity === "not_evaluable" && (
        <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-orange-50 text-orange-900 border border-orange-200">
          {t("common.notEvaluable")}
        </span>
      )}
    </>
  );
}

/** The technical fields behind the two-question summary. */
function ProvenanceDetails({ evaluation, t }: { evaluation: ResponseEvaluation; t: Translate }) {
  const probe = evaluation.baseline_probe;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 space-y-1 text-xs text-slate-700">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <p>
          <span className="font-semibold text-slate-900">{t("results.responseOriginLabel")}:</span>{" "}
          {translated(t, "labels.responseOrigin", evaluation.response_origin)}
        </p>
        <p>
          <span className="font-semibold text-slate-900">{t("results.evaluationValidityLabel")}:</span>{" "}
          {evaluation.evaluation_validity === "not_evaluable" ? t("common.notEvaluable") : t("common.evaluable")}
        </p>
        {evaluation.invalid_reason && (
          <p>
            <span className="font-semibold text-slate-900">{t("results.invalidReasonLabel")}:</span>{" "}
            {translated(t, "labels.invalidReason", evaluation.invalid_reason)}
          </p>
        )}
        {evaluation.matched_signature && (
          <p>
            <span className="font-semibold text-slate-900">{t("results.matchedSignatureLabel")}:</span>{" "}
            <span className="font-mono">{evaluation.matched_signature}</span>
          </p>
        )}
        {evaluation.http_status != null && (
          <p>
            <span className="font-semibold text-slate-900">{t("results.httpStatusLabel")}:</span>{" "}
            <span className="font-mono">{evaluation.http_status}</span>
          </p>
        )}
        {evaluation.content_type && (
          <p>
            <span className="font-semibold text-slate-900">{t("results.contentTypeLabel")}:</span>{" "}
            <span className="font-mono">{evaluation.content_type}</span>
          </p>
        )}
        <p>
          <span className="font-semibold text-slate-900">{t("results.transportLabel")}:</span>{" "}
          {evaluation.transport_ok === false ? "✗" : "✓"}
        </p>
      </div>

      {probe && (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 space-y-1 mt-1">
          <p className="text-xs font-semibold text-slate-900 flex items-center gap-2">
            {t("results.baselineProbeLabel")}
            {probe.cached && (
              <span className="text-[10px] font-normal text-slate-500">({t("results.baselineProbeCachedHint")})</span>
            )}
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            {probe.status === "ok" ? (
              <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-emerald-50 text-emerald-700 border border-emerald-200">
                {t("results.baselineProbeOkLabel")}
              </span>
            ) : probe.status === "failed" ? (
              <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-rose-50 text-rose-700 border border-rose-200">
                {t("results.baselineProbeFailedLabel")}
              </span>
            ) : null}
            {probe.http_status != null && (
              <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-slate-50 text-slate-700 border border-slate-200 font-mono">
                HTTP {probe.http_status}
              </span>
            )}
          </div>
          {probe.reason && (
            <p className="text-xs text-slate-700">
              <span className="font-semibold text-slate-900">{t("results.baselineProbeReasonLabel")}:</span>{" "}
              <span className="font-mono">{probe.reason}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Where a target reply came from: did the attack reach the model, and did
 * the application rewrite the reply. Technical fields sit behind a toggle.
 */
export function ResponseEvaluationPanel({ evaluation, t, variant = "card" }: ResponseEvaluationPanelProps) {
  const _t = t ?? ((key: string) => key);
  const [expanded, setExpanded] = useState(false);
  if (!evaluation) return null;

  const status = resolveProvenanceStatus(evaluation);
  const cfg = STATUS_CONFIG[status];
  const reason = reasonText(evaluation, status, _t);
  const toggle = (
    <button
      type="button"
      aria-expanded={expanded}
      onClick={() => setExpanded(!expanded)}
      className="text-xs text-slate-500 hover:text-slate-700 cursor-pointer"
    >
      {expanded ? "▾ " + _t("common.collapse") : "▸ " + _t("common.expand")}
    </button>
  );

  if (variant === "inline") {
    return (
      <div className="space-y-2 text-xs">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-slate-500">{_t("results.responseProvenance")}</span>
          <cfg.Icon className={`h-3.5 w-3.5 shrink-0 ${cfg.iconClass}`} aria-hidden />
          <span className="font-medium text-slate-800">{_t(cfg.q1Key)}</span>
          {cfg.q2Key && <span className="text-slate-500">{_t(cfg.q2Key)}</span>}
          {reason && <span className="text-slate-500">{reason}</span>}
          {status === "uncertain" && <span className="text-slate-500">{_t("results.provenanceUnknownHint")}</span>}
          <Chips evaluation={evaluation} t={_t} />
          {toggle}
        </div>
        {expanded && <ProvenanceDetails evaluation={evaluation} t={_t} />}
      </div>
    );
  }

  return (
    <div className={`rounded-lg border ${cfg.borderColor} ${cfg.bgColor} p-3 space-y-2`}>
      <p className="text-xs uppercase tracking-wide font-semibold text-slate-600">{_t("results.responseProvenance")}</p>

      {/* Primary two-question display */}
      <div className="space-y-1">
        <div className="flex items-start gap-2">
          <cfg.Icon className={`mt-0.5 h-4 w-4 shrink-0 ${cfg.iconClass}`} aria-hidden />
          <span className="text-sm font-medium text-slate-900">{_t(cfg.q1Key)}</span>
        </div>
        {cfg.q2Key && (
          <div className="flex items-center gap-1.5 ml-6 text-xs text-slate-600">
            {status === "post_processed" ? (
              <PenLine className="h-3.5 w-3.5 shrink-0 text-amber-600" aria-hidden />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" aria-hidden />
            )}
            <span>{_t(cfg.q2Key)}</span>
          </div>
        )}
        {reason && (
          <div className="flex items-start gap-2 ml-6">
            <span className="text-xs text-slate-600">{reason}</span>
          </div>
        )}
        {status === "uncertain" && (
          <p className="text-xs text-slate-500 ml-6">{_t("results.provenanceUnknownHint")}</p>
        )}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <Chips evaluation={evaluation} t={_t} />
      </div>

      {toggle}
      {expanded && <ProvenanceDetails evaluation={evaluation} t={_t} />}
    </div>
  );
}
