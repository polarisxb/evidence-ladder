import { useState } from "react";
import type { ResponseEvaluation } from "../../types";
import { scanStatusLabel, type Translate } from "../../utils/labels";
import { variantClasses, variantLabel } from "../../utils/resultLabels";
import { ResponseEvaluationPanel } from "../ResponseEvaluationPanel";

/** One exchange with the target: a quartet variant, or a stand-alone attack. */
export interface ExchangeView {
  key: string;
  variantType: string;
  isPrimary: boolean;
  request: string;
  response: string | null;
  status?: string | null;
  latencyMs?: number | null;
  evaluation?: ResponseEvaluation | null;
}

function sameEvaluation(a?: ResponseEvaluation | null, b?: ResponseEvaluation | null): boolean {
  if (!a || !b) return !a && !b;
  return a.response_origin === b.response_origin
    && a.evaluation_validity === b.evaluation_validity
    && a.invalid_reason === b.invalid_reason
    && a.model_invoked === b.model_invoked
    && a.post_processed === b.post_processed;
}

/**
 * Request/response of each variant behind tabs, the primary attack first. A
 * variant's own response evaluation is shown only where it differs from the
 * row's, which is already displayed once above.
 */
export function VariantTabs({
  exchanges,
  rowEvaluation,
  t,
}: {
  exchanges: ExchangeView[];
  rowEvaluation?: ResponseEvaluation | null;
  t: Translate;
}) {
  const ordered = [...exchanges].sort((a, b) => Number(b.isPrimary) - Number(a.isPrimary));
  const [activeKey, setActiveKey] = useState(ordered[0]?.key);
  const active = ordered.find((exchange) => exchange.key === activeKey) ?? ordered[0];
  if (!active) return null;

  return (
    <div className="space-y-3">
      {ordered.length > 1 && (
        <div role="tablist" className="flex flex-wrap gap-1.5">
          {ordered.map((exchange) => (
            <button
              key={exchange.key}
              type="button"
              role="tab"
              aria-selected={exchange.key === active.key}
              onClick={() => setActiveKey(exchange.key)}
              className={`px-2.5 py-1 rounded-md text-xs border transition-colors ${
                exchange.key === active.key
                  ? variantClasses(exchange.variantType)
                  : "bg-white text-gray-500 border-gray-200 hover:border-gray-400"
              }`}
            >
              {variantLabel(exchange.variantType, t)}
              {exchange.isPrimary && exchange.variantType !== "attack" && ` · ${t("common.primary")}`}
            </button>
          ))}
        </div>
      )}

      {(active.status || active.latencyMs != null) && (
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          {active.status && <span>{scanStatusLabel(t, active.status)}</span>}
          {active.latencyMs != null && (
            <span className="font-mono">{t("results.latency", { ms: Math.round(active.latencyMs) })}</span>
          )}
        </div>
      )}

      {!sameEvaluation(active.evaluation, rowEvaluation) && (
        <ResponseEvaluationPanel variant="inline" evaluation={active.evaluation} t={t} />
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <p className="mb-1 text-[11px] font-medium text-slate-500">{t("results.requestLabel")}</p>
          <pre className="max-h-60 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-3 font-mono text-xs text-slate-800">
            {active.request}
          </pre>
        </div>
        <div>
          <p className="mb-1 text-[11px] font-medium text-slate-500">{t("results.responseLabel")}</p>
          <pre className="max-h-60 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-3 font-mono text-xs text-slate-800">
            {active.response || t("results.noResponse")}
          </pre>
        </div>
      </div>
    </div>
  );
}
