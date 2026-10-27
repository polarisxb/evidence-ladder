import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import type { AttackCaseDetail, AttackResult } from "../../types";
import { riskLevelLabel, type Translate } from "../../utils/labels";
import {
  businessVerificationClasses,
  businessVerificationLabel,
  controlClasses,
  controlLabel,
  hasBusinessVerification,
  probeCountLabel,
  probeEvidenceChips,
  probeFailureReason,
  probeFailureType,
  scoreTone,
} from "../../utils/resultLabels";
import { reviewActionsFor, type ResultRow, type ReviewAction } from "../../utils/resultRows";
import { resolveResponseEvaluation } from "../../utils/responseEvaluation";
import { riskColors } from "../../utils/risk";
import type { RiskLevel } from "../../types";
import { ResponseEvaluationPanel } from "../ResponseEvaluationPanel";
import { VariantTabs, type ExchangeView } from "./VariantTabs";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h4 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}</h4>
      {children}
    </section>
  );
}

const PILL = "inline-flex px-2 py-0.5 rounded text-[11px]";

const asNumber = (value: unknown): number | null => (typeof value === "number" ? value : null);

function lastTraceResponse(entries: unknown): string | null {
  if (!Array.isArray(entries)) return null;
  for (let i = entries.length - 1; i >= 0; i -= 1) {
    const value = (entries[i] as Record<string, unknown> | null)?.["response"];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
}

/** The target's reply; multi-turn engines keep it in their trace instead of target_response. */
function targetResponse(result: AttackResult): string | null {
  if (result.target_response?.trim()) return result.target_response;
  const raw = result.analysis_raw ?? {};
  return lastTraceResponse(raw["crescendo_turns_detail"])
    ?? lastTraceResponse(raw["pair_attempts"])
    ?? lastTraceResponse(raw["iris_rounds"])
    ?? lastTraceResponse(raw["tap_all_attempts"]);
}

/** Exchanges of a result with no case record: the attack plus any control variants it stored. */
function resultExchanges(result: AttackResult): ExchangeView[] {
  const controls = Array.isArray(result.analysis_raw?.["control_variants"])
    ? (result.analysis_raw["control_variants"] as Array<Record<string, unknown>>)
    : [];
  return [
    {
      key: "attack",
      variantType: "attack",
      isPrimary: true,
      request: result.payload_text,
      response: targetResponse(result),
      evaluation: resolveResponseEvaluation(result),
    },
    ...controls.map((control, index) => ({
      key: `control-${index}`,
      variantType: typeof control["variant"] === "string" ? control["variant"] : `control-${index + 1}`,
      isPrimary: false,
      request: typeof control["prompt"] === "string" ? control["prompt"] : "",
      response: typeof control["response"] === "string" ? control["response"] : null,
    })),
  ];
}

const REVIEW_LABEL_KEYS: Record<ReviewAction, string> = {
  manual_verified: "results.markVerified",
  false_positive: "results.markFalsePositive",
  reset: "results.resetVerdict",
};

const REVIEW_CLASSES: Record<ReviewAction, string> = {
  manual_verified: "border-teal-200 bg-teal-50 text-teal-700 hover:bg-teal-100",
  false_positive: "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100",
  reset: "border-gray-200 bg-white text-gray-700 hover:bg-gray-50",
};

/**
 * Everything about one attack, each fact shown once: verdict and control
 * comparison, scores, business verification, response provenance, the
 * request/response of every quartet variant, manual review, raw data.
 */
export function ResultDetail({
  row,
  detail,
  loading,
  error,
  reviewing,
  onReview,
  t,
}: {
  row: ResultRow;
  detail?: AttackCaseDetail;
  loading: boolean;
  error?: string;
  reviewing: boolean;
  onReview: (action: ReviewAction) => void;
  t: Translate;
}) {
  const { attackCase, result } = row;

  const controlAssessment = attackCase?.control_assessment ?? result?.control_assessment ?? null;
  const finalOutcome = attackCase?.case_final_outcome ?? result?.case_final_outcome ?? null;
  const controlSummary = attackCase?.control_summary ?? result?.control_summary ?? null;
  const quartetPresent = attackCase?.quartet_present ?? result?.quartet_present ?? null;
  const verdictReason = attackCase?.verdict_reason ?? result?.verdict_reason ?? null;

  const riskScore = result?.risk_score ?? detail?.legacy_result?.risk_score ?? null;
  const riskLevel = (row.riskLevel ?? detail?.legacy_result?.risk_level ?? null) as RiskLevel | null;
  const attackGoal = asNumber(result?.analysis_raw?.["attack_goal_score"]) ?? result?.attack_goal_score ?? null;
  const utility = asNumber(result?.analysis_raw?.["utility_score"]) ?? result?.utility_score ?? null;
  const notAutoScored = riskScore === 0
    && (row.verdict === "manual_review_needed" || row.verdict === "ai_suspected" || row.verdict === "not_evaluable");

  const probeSummary = attackCase?.probe_summary ?? result?.probe_summary ?? null;
  const evidenceChips = probeEvidenceChips(
    attackCase?.probe_evidence_preview,
    detail?.probe_evidence_json?.["evidence"],
    result?.probe_evidence_preview,
  );
  const showBusiness = hasBusinessVerification(row.businessStatus) || !!probeFailureReason(probeSummary) || evidenceChips.length > 0;

  const rowEvaluation = resolveResponseEvaluation(detail)
    ?? resolveResponseEvaluation(attackCase)
    ?? resolveResponseEvaluation(result)
    ?? resolveResponseEvaluation(detail?.legacy_result);

  const exchanges: ExchangeView[] | null = attackCase
    ? detail?.variants.map((variant) => ({
        key: variant.id,
        variantType: variant.variant_type,
        isPrimary: variant.is_primary,
        request: variant.request_text,
        response: variant.response_text || variant.response_error,
        status: variant.response_status,
        latencyMs: variant.latency_ms,
        evaluation: resolveResponseEvaluation(variant),
      })) ?? null
    : result ? resultExchanges(result) : null;

  const actions = reviewActionsFor(row);
  const raw = result?.analysis_raw;

  return (
    <div className="space-y-5 text-sm">
      <div className="grid gap-5 lg:grid-cols-2">
        <Section title={t("results.sectionVerdict")}>
          <div className="flex flex-wrap items-center gap-2">
            {quartetPresent != null && (
              <span className={`${PILL} bg-white text-slate-700 border border-slate-200`}>
                {quartetPresent ? t("results.quartetPresent") : t("results.quartetMissing")}
              </span>
            )}
            {controlAssessment && (
              <span className={`${PILL} ${controlClasses(controlAssessment)}`}>{controlLabel(controlAssessment, t)}</span>
            )}
            {/* "passed" / "not_evaluable" outcomes only repeat the row's verdict. */}
            {finalOutcome && finalOutcome !== controlAssessment && finalOutcome !== "passed" && finalOutcome !== "not_evaluable" && (
              <span className={`${PILL} ${controlClasses(finalOutcome)}`}>{controlLabel(finalOutcome, t)}</span>
            )}
            <span className="text-[11px] text-slate-400 font-mono">{row.technique}</span>
          </div>
          {verdictReason && <p className="text-gray-700">{verdictReason}</p>}
          {controlSummary && controlSummary !== verdictReason && (
            <p className="text-slate-600"><span className="text-slate-500">{t("results.controlSummaryLabel")}：</span>{controlSummary}</p>
          )}
          {result?.evidence && result.evidence !== verdictReason && (
            <p className="text-slate-600"><span className="text-slate-500">{t("results.evidenceLabel")}：</span>{result.evidence}</p>
          )}
        </Section>

        <div className="space-y-5">
          <Section title={t("results.sectionScores")}>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              {riskLevel && (
                <span className={`${PILL} ${(riskColors[riskLevel] ?? riskColors.unknown).bg} ${(riskColors[riskLevel] ?? riskColors.unknown).text}`}>
                  {riskLevelLabel(t, riskLevel)}
                </span>
              )}
              {riskScore != null && (
                <span className="text-slate-600">
                  {t("results.riskScoreLabel")}：
                  <span className={`font-mono font-medium ${notAutoScored ? "text-amber-800" : "text-gray-900"}`}>
                    {notAutoScored ? t("results.riskScoreNotAutoScored") : riskScore.toFixed(1)}
                  </span>
                </span>
              )}
              {attackGoal != null && (
                <span className="text-slate-600">
                  {t("report.attackGoalScore")}：<span className={`font-mono font-medium ${scoreTone(attackGoal)}`}>{attackGoal.toFixed(2)}</span>
                </span>
              )}
              {utility != null && (
                <span className="text-slate-600">
                  {t("report.utilityScore")}：<span className="font-mono font-medium text-gray-900">{utility.toFixed(2)}</span>
                </span>
              )}
            </div>
            {notAutoScored && (
              <p className="text-[11px] leading-snug text-slate-500">
                {row.verdict === "not_evaluable" ? t("results.riskScoreTransportHint") : t("results.riskScoreNotAutoScoredHint")}
              </p>
            )}
          </Section>
          {showBusiness && (
            <Section title={t("results.businessVerificationSection")}>
              <div className="flex flex-wrap items-center gap-2">
                {hasBusinessVerification(row.businessStatus) && (
                  <span className={`${PILL} ${businessVerificationClasses(row.businessStatus)}`}>
                    {businessVerificationLabel(row.businessStatus, t)}
                  </span>
                )}
                {probeCountLabel(probeSummary, t) && <span className="text-[11px] text-slate-500">{probeCountLabel(probeSummary, t)}</span>}
                {probeFailureType(probeSummary) && (
                  <span className={`${PILL} bg-white text-slate-700 border border-slate-200 font-mono`}>{probeFailureType(probeSummary)}</span>
                )}
              </div>
              {probeFailureReason(probeSummary) && <p className="text-slate-700">{probeFailureReason(probeSummary)}</p>}
              {evidenceChips.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {evidenceChips.map((chip) => (
                    <span key={chip} className={`${PILL} bg-white text-slate-700 border border-slate-200`}>{chip}</span>
                  ))}
                </div>
              )}
            </Section>
          )}
        </div>
      </div>

      <Section title={t("results.sectionExchange")}>
        {rowEvaluation && <ResponseEvaluationPanel variant="inline" evaluation={rowEvaluation} t={t} />}
        {loading ? (
          <div className="flex items-center gap-2 text-slate-600"><Loader2 className="h-4 w-4 animate-spin" />{t("results.loadingDetails")}</div>
        ) : error ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-rose-800">{t("results.failedToLoadDetails")}：{error}</p>
        ) : exchanges && exchanges.length > 0 ? (
          <VariantTabs exchanges={exchanges} rowEvaluation={rowEvaluation} t={t} />
        ) : null}
      </Section>

      {actions.length > 0 && (
        <Section title={t("results.sectionReview")}>
          <div className="flex flex-wrap gap-2">
            {actions.map((action) => (
              <button
                key={action}
                type="button"
                disabled={reviewing}
                onClick={() => onReview(action)}
                className={`px-3 py-1.5 text-xs rounded-lg border disabled:opacity-50 transition-colors ${REVIEW_CLASSES[action]}`}
              >
                {t(REVIEW_LABEL_KEYS[action])}
              </button>
            ))}
          </div>
        </Section>
      )}

      {raw && Object.keys(raw).length > 0 && (
        <details className="group">
          <summary className="cursor-pointer select-none text-[11px] font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-700">
            {t("results.rawData")}
          </summary>
          <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-3 font-mono text-xs text-slate-800">
            {JSON.stringify(raw, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
