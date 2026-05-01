import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Download,
  Filter,
  Loader2,
  Shield,
  XCircle,
} from "lucide-react";
import { getCaseDetail, getScanCases } from "../api/cases";
import { getAttackResults, reviewAttackResult } from "../api/reports";
import { ResponseEvaluationPanel } from "../components/ResponseEvaluationPanel";
import { ResultSemanticsCard } from "../components/ResultSemanticsCard";
import { getScan } from "../api/scans";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";
import { buildCsvString, downloadCsv } from "../utils/csv";
import {
  resolveResponseEvaluation,
  notEvaluableDisplayCategory,
  notEvaluableToneClasses,
  type NotEvaluableDisplayCategory,
} from "../utils/responseEvaluation";
import { riskColors } from "../utils/risk";
import type { AttackCase, AttackCaseDetail, AttackCaseVariant, AttackResult, RiskLevel, ScanTask } from "../types";

type VerdictFilter =
  | "all"
  | "confirmed"
  | "rule_verified"
  | "manual_verified"
  | "ai_suspected"
  | "manual_review_needed"
  | "false_positive"
  | "passed"
  | "not_evaluable";

type ProbeFilter = "all" | "text_claim_only" | "probe_verified" | "probe_failed" | "probe_inconclusive";

const VALID_VERDICT_FILTERS: ReadonlySet<VerdictFilter> = new Set([
  "all",
  "confirmed",
  "rule_verified",
  "manual_verified",
  "ai_suspected",
  "manual_review_needed",
  "false_positive",
  "passed",
  "not_evaluable",
]);

function normalizeVerdictFilter(value: string | null): VerdictFilter {
  return value && VALID_VERDICT_FILTERS.has(value as VerdictFilter)
    ? (value as VerdictFilter)
    : "all";
}

// "confirmed" is a composite bucket that matches the Report page's
// headline "Confirmed Findings" card (rule_verified + manual_verified
// + ai_suspected). All other values are single verdict_status matches.
function verdictFilterMatches(filter: VerdictFilter, resolved: string): boolean {
  if (filter === "all") return true;
  if (filter === "confirmed") {
    return (
      resolved === "rule_verified" ||
      resolved === "manual_verified" ||
      resolved === "ai_suspected"
    );
  }
  return resolved === filter;
}

function resolvedVerdictStatus(result: AttackResult): NonNullable<AttackResult["verdict_status"]> {
  // Primary attack not flagged successful: show defense "passed" only when the engine is confident.
  // Do not collapse manual_review_needed / ai_suspected / rule_verified — inconclusive ≠ defense win.
  if (result.verdict_status === "not_evaluable") {
    return "not_evaluable";
  }
  if (!result.attack_successful) {
    if (
      result.verdict_status === "manual_verified" ||
      result.verdict_status === "false_positive" ||
      result.verdict_status === "manual_review_needed" ||
      result.verdict_status === "ai_suspected" ||
      result.verdict_status === "rule_verified"
    ) {
      return result.verdict_status;
    }
    return "passed";
  }
  if (result.verdict_status) return result.verdict_status;
  return "manual_review_needed";
}

function resolvedCaseVerdictStatus(attackCase: AttackCase): NonNullable<AttackResult["verdict_status"]> {
  if (attackCase.verdict_status === "not_evaluable") {
    return "not_evaluable";
  }
  if (!attackCase.primary_attack_successful) {
    if (
      attackCase.verdict_status === "manual_verified" ||
      attackCase.verdict_status === "false_positive" ||
      attackCase.verdict_status === "manual_review_needed" ||
      attackCase.verdict_status === "ai_suspected" ||
      attackCase.verdict_status === "rule_verified"
    ) {
      return attackCase.verdict_status;
    }
    return "passed";
  }
  if (attackCase.verdict_status) return attackCase.verdict_status;
  return "manual_review_needed";
}

function verdictLabel(status: AttackResult["verdict_status"], t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  switch (status) {
    case "rule_verified": return _t("common.ruleVerified");
    case "manual_verified": return _t("common.manualVerified");
    case "ai_suspected": return _t("common.aiSuspected");
    case "manual_review_needed": return _t("common.manualReviewNeeded");
    case "false_positive": return _t("common.falsePositive");
    case "passed": return _t("common.passed");
    case "not_evaluable": return _t("common.notEvaluable");
    default: return _t("common.unclassified");
  }
}

function verdictClasses(status: AttackResult["verdict_status"]) {
  switch (status) {
    case "rule_verified":
      return "bg-emerald-50 text-emerald-700 border border-emerald-200";
    case "manual_verified":
      return "bg-teal-50 text-teal-700 border border-teal-200";
    case "ai_suspected":
      return "bg-amber-50 text-amber-800 border border-amber-200";
    case "manual_review_needed":
      return "bg-slate-100 text-slate-700 border border-slate-200";
    case "false_positive":
      return "bg-rose-50 text-rose-700 border border-rose-200";
    case "passed":
      return "bg-gray-100 text-gray-600 border border-gray-200";
    case "not_evaluable":
      return "bg-orange-50 text-orange-900 border border-orange-200";
    default:
      return "bg-gray-100 text-gray-600 border border-gray-200";
  }
}

function controlLabel(value: AttackResult["control_assessment"] | AttackCase["case_final_outcome"], t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  switch (value) {
    case "rule_verified_finding": return _t("common.ruleVerifiedFinding");
    case "attack_delta_supported": return _t("common.attackDeltaSupported");
    case "discussion_supported": return _t("common.discussionSupported");
    case "controls_inconclusive": return _t("common.controlsInconclusive");
    case "controls_missing": return _t("common.controlsMissing");
    case "passed": return _t("common.passed");
    case "not_evaluable": return _t("common.notEvaluable");
    default: return _t("common.controlSummary");
  }
}

function controlClasses(value: AttackResult["control_assessment"] | AttackCase["case_final_outcome"]) {
  switch (value) {
    case "rule_verified_finding":
      return "bg-emerald-50 text-emerald-700 border border-emerald-200";
    case "attack_delta_supported":
      return "bg-emerald-50 text-emerald-700 border border-emerald-200";
    case "discussion_supported":
      return "bg-sky-50 text-sky-700 border border-sky-200";
    case "controls_inconclusive":
      return "bg-amber-50 text-amber-800 border border-amber-200";
    case "controls_missing":
    case "passed":
      return "bg-gray-100 text-gray-600 border border-gray-200";
    case "not_evaluable":
      return "bg-orange-50 text-orange-900 border border-orange-200";
    default:
      return "bg-gray-100 text-gray-600 border border-gray-200";
  }
}

/**
 * Two-pill rendering for a ``not_evaluable`` case in the list views.
 *
 * The main pill carries the refined category label (e.g. "Transport
 * failure" / "Empty reply · target healthy"). The optional secondary
 * pill carries operator-facing hints assembled from the available
 * envelope + baseline-probe fields: ``HTTP 502``, ``target online``,
 * or the matched signature — whichever is non-empty.
 *
 * This replaces the legacy behaviour where both the ``case_final_outcome``
 * pill and the ``verdict_status`` pill showed an identical "无法评测"
 * label, which gave the operator no way to tell apart model silence,
 * gateway errors, or an offline target without expanding the case.
 */
function NotEvaluablePills({
  category,
  t,
}: {
  category: NotEvaluableDisplayCategory;
  t: (key: string) => string;
}) {
  const toneCls = notEvaluableToneClasses(category.tone);
  const i18nLabel = t(category.labelKey);
  const mainText = i18nLabel && i18nLabel !== category.labelKey ? i18nLabel : category.fallbackLabel;

  const hints: string[] = [];
  if (category.httpStatus != null) {
    hints.push(`HTTP ${category.httpStatus}`);
  }
  if (category.probeStatus === "ok") {
    hints.push(t("results.notEvaluableCategory.targetOnline"));
  } else if (category.probeStatus === "failed") {
    hints.push(t("results.notEvaluableCategory.targetOffline"));
  }
  if (category.matchedSignature) {
    hints.push(category.matchedSignature);
  }
  const sepRaw = t("results.notEvaluableCategory.suffixSeparator");
  const sep = sepRaw && sepRaw !== "results.notEvaluableCategory.suffixSeparator" ? sepRaw : "·";

  return (
    <>
      <span className={`text-[11px] px-2 py-0.5 rounded ${toneCls}`}>{mainText}</span>
      {hints.length > 0 && (
        <span className="text-[11px] px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200 font-mono">
          {hints.join(` ${sep} `)}
        </span>
      )}
    </>
  );
}

function variantLabel(variantType: AttackCaseVariant["variant_type"], t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  switch (variantType) {
    case "attack":
      return _t("common.attack");
    case "clean":
      return _t("common.clean");
    case "quoted_attack":
      return _t("common.quotedAttack");
    case "benign_distractor":
      return _t("common.benignDistractor");
    default:
      return variantType;
  }
}

function variantClasses(variantType: AttackCaseVariant["variant_type"]) {
  switch (variantType) {
    case "attack":
      return "bg-red-50 text-red-700 border border-red-200";
    case "clean":
      return "bg-emerald-50 text-emerald-700 border border-emerald-200";
    case "quoted_attack":
      return "bg-amber-50 text-amber-800 border border-amber-200";
    case "benign_distractor":
      return "bg-sky-50 text-sky-700 border border-sky-200";
    default:
      return "bg-gray-100 text-gray-600 border border-gray-200";
  }
}

function businessVerificationLabel(status?: string | null, t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  switch (status) {
    case "text_claim_only":
      return _t("common.textClaimOnly");
    case "probe_verified":
      return _t("common.probeVerified");
    case "probe_failed":
      return _t("common.probeFailed");
    case "probe_inconclusive":
      return _t("common.probeInconclusive");
    default:
      return _t("common.notApplicable");
  }
}

function businessVerificationClasses(status?: string | null) {
  switch (status) {
    case "text_claim_only":
      return "bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200";
    case "probe_verified":
      return "bg-emerald-50 text-emerald-700 border border-emerald-200";
    case "probe_failed":
      return "bg-rose-50 text-rose-700 border border-rose-200";
    case "probe_inconclusive":
      return "bg-amber-50 text-amber-800 border border-amber-200";
    default:
      return "bg-gray-100 text-gray-600 border border-gray-200";
  }
}

function extractTraceResponse(entries: unknown) {
  if (!Array.isArray(entries)) return null;
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    const entry = entries[index];
    if (entry && typeof entry === "object") {
      const value = (entry as Record<string, unknown>)["response"];
      if (typeof value === "string" && value.trim()) return value;
    }
  }
  return null;
}

function resolvedTargetResponse(result: AttackResult) {
  if (typeof result.target_response === "string" && result.target_response.trim()) return result.target_response;
  return (
    extractTraceResponse(result.analysis_raw?.["crescendo_turns_detail"]) ||
    extractTraceResponse(result.analysis_raw?.["pair_attempts"]) ||
    extractTraceResponse(result.analysis_raw?.["iris_rounds"]) ||
    extractTraceResponse(result.analysis_raw?.["tap_all_attempts"]) ||
    null
  );
}

function scoreTone(score: number | null | undefined) {
  if (score == null) return "text-gray-500";
  if (score >= 0.8) return "text-red-600";
  if (score >= 0.5) return "text-orange-600";
  if (score >= 0.2) return "text-amber-700";
  return "text-green-600";
}

function probeFailureType(probeSummary?: Record<string, unknown> | null) {
  return typeof probeSummary?.["failure_type"] === "string" ? probeSummary["failure_type"] : null;
}

function probeFailureReason(probeSummary?: Record<string, unknown> | null) {
  return typeof probeSummary?.["failure_reason"] === "string" ? probeSummary["failure_reason"] : null;
}

function probeEvidenceItems(probeEvidence?: Record<string, unknown> | null) {
  const evidence = probeEvidence?.["evidence"];
  if (!Array.isArray(evidence)) return [];
  return evidence.filter((entry): entry is Record<string, unknown> => !!entry && typeof entry === "object");
}

function probeCountLabel(probeSummary?: Record<string, unknown> | null) {
  const verified =
    typeof probeSummary?.["verified_assertion_count"] === "number"
      ? probeSummary["verified_assertion_count"]
      : null;
  const total =
    typeof probeSummary?.["total_assertion_count"] === "number"
      ? probeSummary["total_assertion_count"]
      : null;
  const steps =
    typeof probeSummary?.["step_count"] === "number" ? probeSummary["step_count"] : null;

  // 全为 0 或均为 null（非 probe 场景）时不显示
  if ((total ?? 0) === 0 && (steps ?? 0) === 0) return "";

  const parts = [
    verified != null && total != null ? `${verified}/${total} assertions` : null,
    steps != null ? `${steps} step${steps === 1 ? "" : "s"}` : null,
  ].filter(Boolean);

  return parts.join(" | ");
}

function renderCaseDetail(detail: AttackCaseDetail | undefined, loading: boolean, error?: string, t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  if (loading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 flex items-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin" />
        {_t("results.loadingDetails")}
      </div>
    );
  }
  if (error) {
    return <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>;
  }
  if (!detail) return null;

  const hasProbeData = detail.business_verification_status && detail.business_verification_status !== "not_applicable";
  const hasProbeEvidence = probeEvidenceItems(detail.probe_evidence_json).length > 0;
  const hasProbeFailure = !!probeFailureReason(detail.probe_summary) || !!probeFailureType(detail.probe_summary);
  const detailResponseEvaluation =
    resolveResponseEvaluation(detail) ||
    resolveResponseEvaluation(detail.legacy_result) ||
    resolveResponseEvaluation(detail.summary_json);

  return (
    <div className="space-y-3">
      <ResponseEvaluationPanel evaluation={detailResponseEvaluation} t={_t} />
      {(hasProbeData || hasProbeEvidence || hasProbeFailure) ? (
        <div className="rounded-lg border border-fuchsia-100 bg-fuchsia-50/70 p-3 space-y-2">
          <p className="text-xs text-fuchsia-700 uppercase tracking-wide font-semibold">{_t("results.businessVerificationSection")}</p>
          <div className="flex items-center gap-2 flex-wrap">
            {hasProbeData && (
              <span
                className={`inline-flex px-2 py-0.5 rounded text-[11px] ${businessVerificationClasses(
                  detail.business_verification_status,
                )}`}
              >
                {businessVerificationLabel(detail.business_verification_status, _t)}
              </span>
            )}
            {probeCountLabel(detail.probe_summary) && (
              <span className="text-[11px] text-slate-500">{probeCountLabel(detail.probe_summary)}</span>
            )}
            {probeFailureType(detail.probe_summary) && (
              <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200 font-mono">
                {probeFailureType(detail.probe_summary)}
              </span>
            )}
          </div>
          {probeFailureReason(detail.probe_summary) && (
            <p className="text-sm text-slate-700">{probeFailureReason(detail.probe_summary)}</p>
          )}
          {hasProbeEvidence && (
            <div className="flex items-center gap-2 flex-wrap">
              {probeEvidenceItems(detail.probe_evidence_json)
                .slice(0, 4)
                .map((entry, index) => (
                  <span
                    key={`${detail.id}-probe-${index}`}
                    className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200"
                  >
                    {typeof entry["kind"] === "string" ? entry["kind"] : "evidence"}
                    {typeof entry["step"] === "string" ? ` @ ${entry["step"]}` : ""}
                  </span>
                ))}
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-slate-400">{_t("results.probeNotConfigured")}</p>
      )}
      {detail.variants.map((variant) => (
        <div key={variant.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`inline-flex px-2 py-0.5 rounded text-[11px] ${variantClasses(variant.variant_type)}`}>
              {variantLabel(variant.variant_type, _t)}
            </span>
            {variant.is_primary && (
              <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200">
                {_t("common.primary")}
              </span>
            )}
            {variant.response_status && (
              <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200">
                {variant.response_status}
              </span>
            )}
            {variant.latency_ms != null && (
              <span className="text-[11px] text-slate-500 font-mono">{variant.latency_ms.toFixed(0)} ms</span>
            )}
          </div>
          <ResponseEvaluationPanel evaluation={resolveResponseEvaluation(variant)} t={_t} />
          <div className="grid grid-cols-2 gap-4">
            <pre className="bg-white border border-slate-200 p-3 rounded-lg text-slate-800 font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
              {variant.request_text}
            </pre>
            <pre className="bg-white border border-slate-200 p-3 rounded-lg text-slate-800 font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
              {variant.response_text || variant.response_error || "(no response)"}
            </pre>
          </div>
        </div>
      ))}
      {detail.legacy_result && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
          <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold">{_t("results.analysisSummary")}</p>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs text-slate-600">
              {_t("results.riskScoreLabel")}:{" "}
              {detail.legacy_result.verdict_status &&
              (detail.legacy_result.verdict_status === "manual_review_needed" ||
                detail.legacy_result.verdict_status === "ai_suspected" ||
                detail.legacy_result.verdict_status === "not_evaluable") &&
              detail.legacy_result.risk_score === 0 ? (
                <span className="font-mono font-medium text-amber-800">{_t("results.riskScoreNotAutoScored")}</span>
              ) : (
                <span className="font-mono font-medium">{detail.legacy_result.risk_score.toFixed(1)}</span>
              )}
            </span>
            {detail.legacy_result.verdict_status && (
              <span className={`text-[11px] px-2 py-0.5 rounded ${verdictClasses(detail.legacy_result.verdict_status)}`}>
                {verdictLabel(detail.legacy_result.verdict_status, _t)}
              </span>
            )}
          </div>
          {JSON.stringify(resolveResponseEvaluation(detail.legacy_result)) !== JSON.stringify(detailResponseEvaluation) && (
            <ResponseEvaluationPanel evaluation={resolveResponseEvaluation(detail.legacy_result)} t={_t} />
          )}
          {detail.legacy_result.verdict_status &&
            (detail.legacy_result.verdict_status === "manual_review_needed" ||
              detail.legacy_result.verdict_status === "ai_suspected") &&
            detail.legacy_result.risk_score === 0 && (
              <p className="text-[11px] text-slate-500 leading-snug">{_t("results.riskScoreNotAutoScoredHint")}</p>
            )}
          {detail.legacy_result.verdict_status === "not_evaluable" && detail.legacy_result.risk_score === 0 && (
            <p className="text-[11px] text-slate-500 leading-snug">{_t("results.riskScoreTransportHint")}</p>
          )}
          {detail.legacy_result.target_response && (
            <div>
              <p className="text-xs text-slate-500 mb-1">{_t("results.targetResponseLabel")}:</p>
              <pre className="bg-white border border-slate-200 p-3 rounded-lg text-slate-800 font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
                {detail.legacy_result.target_response}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ScanResults() {
  const { scanId } = useParams<{ scanId: string }>();
  const [scan, setScan] = useState<ScanTask | null>(null);
  const [results, setResults] = useState<AttackResult[]>([]);
  const [cases, setCases] = useState<AttackCase[]>([]);
  const [caseDetails, setCaseDetails] = useState<Record<string, AttackCaseDetail>>({});
  const [caseDetailErrors, setCaseDetailErrors] = useState<Record<string, string>>({});
  const [caseDetailLoading, setCaseDetailLoading] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"cases" | "legacy">("cases");
  const [expandedCases, setExpandedCases] = useState<Set<string>>(new Set());
  const [expandedLegacy, setExpandedLegacy] = useState<Set<string>>(new Set());
  const [searchParams, setSearchParams] = useSearchParams();
  // Deep-link support: the Report page's "Confirmed / Needs Review / False
  // Positive" cards link here with ?verdict=<bucket>. Unknown or missing
  // values fall back to "all" so pasted URLs never crash the page.
  const [filter, setFilter] = useState<VerdictFilter>(() =>
    normalizeVerdictFilter(searchParams.get("verdict")),
  );
  const [probeFilter, setProbeFilter] = useState<ProbeFilter>("all");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const navigate = useNavigate();
  const { toast } = useToast();
  const { t } = useLocale();

  function updateFilter(next: VerdictFilter) {
    setFilter(next);
    // Keep the URL in sync so the current filter is shareable / bookmarkable.
    setSearchParams(
      (prev) => {
        const copy = new URLSearchParams(prev);
        if (next === "all") copy.delete("verdict");
        else copy.set("verdict", next);
        return copy;
      },
      { replace: true },
    );
  }

  function handleExportCsv() {
    if (viewMode === "cases") {
      const headers = [
        "attack_name", "category", "technique",
        "verdict_status", "case_final_outcome", "primary_attack_successful",
        "business_verification_status", "control_assessment", "response_origin", "invalid_reason",
        "quartet_present", "variant_count", "created_at",
      ];
      const rows = filteredCases.map((c) => ({
        attack_name: c.attack_name,
        category: c.category,
        technique: c.technique,
        verdict_status: c.verdict_status ?? "",
        case_final_outcome: c.case_final_outcome ?? "",
        primary_attack_successful: c.primary_attack_successful ?? "",
        business_verification_status: c.business_verification_status ?? "",
        control_assessment: c.control_assessment ?? "",
        response_origin: resolveResponseEvaluation(c)?.response_origin ?? "",
        invalid_reason: resolveResponseEvaluation(c)?.invalid_reason ?? "",
        quartet_present: c.quartet_present,
        variant_count: c.variant_count,
        created_at: c.created_at,
      }));
      downloadCsv(`scan-${scanId}-cases.csv`, buildCsvString(headers, rows));
    } else {
      const headers = [
        "attack_name", "category", "technique",
        "attack_successful", "risk_level", "risk_score",
        "verdict_status", "business_verification_status", "response_origin", "invalid_reason",
        "payload_text", "created_at",
      ];
      const rows = filteredResults.map((r) => ({
        attack_name: r.attack_name,
        category: r.category,
        technique: r.technique,
        attack_successful: r.attack_successful,
        risk_level: r.risk_level,
        risk_score: r.risk_score,
        verdict_status: r.verdict_status ?? "",
        business_verification_status: r.business_verification_status ?? "",
        response_origin: resolveResponseEvaluation(r)?.response_origin ?? "",
        invalid_reason: resolveResponseEvaluation(r)?.invalid_reason ?? "",
        payload_text: r.payload_text,
        created_at: r.created_at,
      }));
      downloadCsv(`scan-${scanId}-results.csv`, buildCsvString(headers, rows));
    }
  }

  useEffect(() => {
    if (!scanId) return;
    Promise.all([
      getScan(scanId).catch(() => null),
      getAttackResults(scanId).catch(() => []),
      getScanCases(scanId).catch(() => []),
    ])
      .then(([scanTask, attackResults, attackCases]) => {
        setScan(scanTask);
        setResults(attackResults);
        setCases(attackCases);
      })
      .catch((err) => toast("error", `${t("results.title")}: ${err.message}`))
      .finally(() => setLoading(false));
  }, [scanId, toast]);

  // Deep-link from the Judge Calibration page: ?case=<attack_case_id>.
  // Once the case list is loaded, we expand the target row, fetch its
  // detail, scroll it into view, and — if the active filter would hide
  // it — reset the filter to "all". The ref guards against re-scrolling
  // every time a piece of state updates (expand state, filter, …).
  const deepLinkedCaseRef = useRef<string | null>(null);
  useEffect(() => {
    const targetCaseId = searchParams.get("case");
    if (!targetCaseId) return;
    if (deepLinkedCaseRef.current === targetCaseId) return;
    if (cases.length === 0) return; // wait until cases are loaded

    const found = cases.find((c) => c.id === targetCaseId);
    if (!found) {
      // Case was deleted or belongs to another scan — mark handled and
      // leave the page in its default state.
      deepLinkedCaseRef.current = targetCaseId;
      return;
    }

    // Ensure we're on the Cases view, not Legacy.
    setViewMode("cases");
    // If the active verdict filter would hide this case, relax it so the
    // user can actually see what they deep-linked to.
    if (!verdictFilterMatches(filter, resolvedCaseVerdictStatus(found))) {
      setFilter("all");
    }
    setExpandedCases((prev) => new Set(prev).add(targetCaseId));
    void ensureCaseDetail(targetCaseId);

    // Let the browser paint the expanded section before scrolling.
    setTimeout(() => {
      const el = document.getElementById(`case-${targetCaseId}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);

    deepLinkedCaseRef.current = targetCaseId;
    // We intentionally *don't* depend on ``filter`` — resetting it above
    // would otherwise retrigger and fight user interaction afterwards.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cases, searchParams]);

  async function ensureCaseDetail(caseId: string) {
    if (caseDetails[caseId] || caseDetailLoading.has(caseId)) return;
    setCaseDetailLoading((prev) => new Set(prev).add(caseId));
    try {
      const detail = await getCaseDetail(caseId);
      setCaseDetails((prev) => ({ ...prev, [caseId]: detail }));
      setCaseDetailErrors((prev) => {
        const next = { ...prev };
        delete next[caseId];
        return next;
      });
    } catch (err) {
      setCaseDetailErrors((prev) => ({ ...prev, [caseId]: err instanceof Error ? err.message : String(err) }));
    } finally {
      setCaseDetailLoading((prev) => {
        const next = new Set(prev);
        next.delete(caseId);
        return next;
      });
    }
  }

  function toggleCase(caseId: string) {
    const isOpen = expandedCases.has(caseId);
    setExpandedCases((prev) => {
      const next = new Set(prev);
      next.has(caseId) ? next.delete(caseId) : next.add(caseId);
      return next;
    });
    if (!isOpen) void ensureCaseDetail(caseId);
  }

  function toggleLegacy(resultId: string) {
    setExpandedLegacy((prev) => {
      const next = new Set(prev);
      next.has(resultId) ? next.delete(resultId) : next.add(resultId);
      return next;
    });
  }

  async function handleReviewAction(resultId: string, action: "manual_verified" | "false_positive" | "reset") {
    setReviewingId(resultId);
    try {
      const updated = await reviewAttackResult(resultId, action);
      setResults((prev) => prev.map((item) => (item.id === resultId ? updated : item)));
      // 同步更新 Cases 视图中关联该 legacy result 的 case
      setCases((prev) =>
        prev.map((c) =>
          c.legacy_attack_result_id === resultId
            ? {
                ...c,
                verdict_status: updated.verdict_status ?? undefined,
                primary_attack_successful: updated.attack_successful,
              }
            : c,
        ),
      );
      toast("success", t("results.reviewUpdated"));
    } catch (err) {
      toast("error", `${t("results.failedToReview")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setReviewingId(null);
    }
  }

  if (loading) return <div className="text-center text-gray-500 py-12">{t("common.loading")}</div>;

  const categories = [
    ...new Set((viewMode === "cases" ? cases : results).map((item) => item.category)),
  ];
  const filteredCases = cases.filter((item) =>
    verdictFilterMatches(filter, resolvedCaseVerdictStatus(item)) &&
    (probeFilter === "all" || item.business_verification_status === probeFilter) &&
    (!categoryFilter || item.category === categoryFilter),
  );
  const filteredResults = results.filter((item) =>
    verdictFilterMatches(filter, resolvedVerdictStatus(item)) &&
    (probeFilter === "all" || item.business_verification_status === probeFilter) &&
    (!categoryFilter || item.category === categoryFilter),
  );
  const activeItems = viewMode === "cases" ? cases : results;
  const resolveStatus = (item: AttackCase | AttackResult): string =>
    "primary_attack_successful" in item
      ? resolvedCaseVerdictStatus(item as AttackCase)
      : resolvedVerdictStatus(item as AttackResult);
  const verdictCounts = {
    rule_verified: activeItems.filter((item) => resolveStatus(item) === "rule_verified").length,
    manual_verified: activeItems.filter((item) => resolveStatus(item) === "manual_verified").length,
    ai_suspected: activeItems.filter((item) => resolveStatus(item) === "ai_suspected").length,
    manual_review_needed: activeItems.filter((item) => resolveStatus(item) === "manual_review_needed").length,
    false_positive: activeItems.filter((item) => resolveStatus(item) === "false_positive").length,
    passed: activeItems.filter((item) => resolveStatus(item) === "passed").length,
    not_evaluable: activeItems.filter((item) => resolveStatus(item) === "not_evaluable").length,
  };
  // Composite bucket matching the Report page's "Confirmed Findings" card.
  const confirmedCount =
    verdictCounts.rule_verified + verdictCounts.manual_verified + verdictCounts.ai_suspected;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        {/* Back button behavior depends on where the user came from.
            For deep-links from Judge Calibration (``?back=calibration``)
            we call ``navigate(-1)`` so the browser pops history (preserves
            scroll position + shrinks history stack, no duplicate entries).
            For everyone else we go to the Report page as before. */}
        <button
          type="button"
          onClick={() => {
            if (searchParams.get("back") === "calibration") {
              navigate(-1);
            } else {
              navigate(`/report/${scanId}`);
            }
          }}
          className="text-gray-400 hover:text-gray-700 transition-colors"
          aria-label="back"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">{t("results.title")}</h1>
          <p className="text-sm text-gray-500">
            {scan?.name} - {cases.length} {t("results.casesSuffix")}, {results.length} {t("results.legacySuffix")}, {results.filter((item) => item.attack_successful).length} {t("results.vulnerabilitiesSuffix")}
          </p>
          {scan && (
            <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
              <span className={`px-2 py-0.5 rounded-full border ${scan.target_type === "adapter" ? "bg-sky-50 text-sky-700 border-sky-200" : scan.target_type === "custom" ? "bg-amber-50 text-amber-800 border-amber-200" : "bg-gray-100 text-gray-700 border-gray-200"}`}>
                {scan.target_type === "adapter" ? t("adapters.adapterScan") : scan.target_type === "custom" ? t("scanProgress.legacyCustom") : scan.target_type}
              </span>
              <span className="font-mono">{scan.target_url}</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button type="button" onClick={() => setViewMode("cases")} className={`px-4 py-2 rounded-lg text-sm border transition-colors ${viewMode === "cases" ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-200 hover:border-gray-400"}`}>
          {t("results.casesTab")} ({cases.length})
        </button>
        <button type="button" onClick={() => setViewMode("legacy")} className={`px-4 py-2 rounded-lg text-sm border transition-colors ${viewMode === "legacy" ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-200 hover:border-gray-400"}`}>
          {t("results.legacyTab")} ({results.length})
        </button>
        <button
          type="button"
          onClick={handleExportCsv}
          className="ml-auto flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm border border-gray-200 bg-white text-gray-700 hover:border-gray-400 transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          {t("results.exportCsv")}
        </button>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <Filter className="w-4 h-4 text-gray-400" />
        <div className="flex gap-1 flex-wrap">
          {(["all", "confirmed", "rule_verified", "manual_verified", "ai_suspected", "manual_review_needed", "false_positive", "passed", "not_evaluable"] as const).map((value) => {
            // The composite "confirmed" chip uses an orange accent so it reads
            // as the same bucket the Report page highlights as "Confirmed
            // Findings" — and stays visually distinct from the three single
            // verdict_status chips it aggregates.
            const isActive = filter === value;
            const isComposite = value === "confirmed";
            const chipClass = isActive
              ? isComposite
                ? "bg-orange-50 text-orange-800 border border-orange-200"
                : "bg-indigo-50 text-indigo-800 border border-indigo-200"
              : "text-gray-500 hover:text-gray-800";
            return (
              <button key={value} onClick={() => updateFilter(value)} className={`px-3 py-1 text-xs rounded-md transition-colors ${chipClass}`}>
                {value === "all" && `${t("results.filterAll")} (${activeItems.length})`}
                {value === "confirmed" && `${t("results.filterConfirmed")} (${confirmedCount})`}
                {value === "rule_verified" && `${t("results.filterVerified")} (${verdictCounts.rule_verified})`}
                {value === "manual_verified" && `${t("results.filterManualVerified")} (${verdictCounts.manual_verified})`}
                {value === "ai_suspected" && `${t("results.filterAiSuspected")} (${verdictCounts.ai_suspected})`}
                {value === "manual_review_needed" && `${t("results.filterNeedsReview")} (${verdictCounts.manual_review_needed})`}
                {value === "false_positive" && `${t("results.filterFalsePositive")} (${verdictCounts.false_positive})`}
                {value === "passed" && `${t("results.filterPassed")} (${verdictCounts.passed})`}
                {value === "not_evaluable" && `${t("results.filterNotEvaluable")} (${verdictCounts.not_evaluable})`}
              </button>
            );
          })}
        </div>
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="ml-auto px-3 py-1 text-xs bg-white border border-gray-200 rounded-lg text-gray-900 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10 shadow-sm">
          <option value="">{t("results.allCategories")}</option>
          {categories.map((category) => (
            <option key={category} value={category}>
              {category.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">{t("results.businessVerification")}</span>
        {(["all", "text_claim_only", "probe_verified", "probe_failed", "probe_inconclusive"] as const).map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setProbeFilter(value)}
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              probeFilter === value
                ? "bg-fuchsia-50 text-fuchsia-800 border border-fuchsia-200"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            {value === "all" ? t("common.all") : businessVerificationLabel(value, t)}
          </button>
        ))}
      </div>

      <ResultSemanticsCard t={t} />

      {viewMode === "cases" ? (
        <div className="card divide-y divide-gray-100">
          {filteredCases.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              {cases.length === 0 ? t("results.noCase") : t("results.noMatch")}
            </div>
          ) : (
            filteredCases.map((attackCase) => (
              <div key={attackCase.id} id={`case-${attackCase.id}`} className="scroll-mt-4">
                <button onClick={() => toggleCase(attackCase.id)} className="w-full flex items-center gap-3 p-4 text-left hover:bg-gray-50 transition-colors">
                  {attackCase.primary_attack_successful ? <XCircle className="w-4 h-4 text-red-500 shrink-0" /> : <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-900 truncate">{attackCase.attack_name}</p>
                    <p className="text-xs text-gray-500">{attackCase.technique} · {attackCase.template_id}</p>
                  </div>
                  {attackCase.case_final_outcome
                    && attackCase.case_final_outcome !== "passed"
                    && attackCase.case_final_outcome !== "not_evaluable" && (
                    <span className={`text-[11px] px-2 py-0.5 rounded ${controlClasses(attackCase.case_final_outcome)}`}>{controlLabel(attackCase.case_final_outcome, t)}</span>
                  )}
                  {attackCase.business_verification_status && attackCase.business_verification_status !== "not_applicable" && (
                    <span className={`text-[11px] px-2 py-0.5 rounded ${businessVerificationClasses(attackCase.business_verification_status)}`}>
                      {businessVerificationLabel(attackCase.business_verification_status, t)}
                    </span>
                  )}
                  {(() => {
                    const _vStatus = resolvedCaseVerdictStatus(attackCase);
                    if (_vStatus === "not_evaluable") {
                      const _cat = notEvaluableDisplayCategory(resolveResponseEvaluation(attackCase));
                      if (_cat) return <NotEvaluablePills category={_cat} t={t} />;
                    }
                    return (
                      <span className={`text-[11px] px-2 py-0.5 rounded ${verdictClasses(_vStatus)}`}>{verdictLabel(_vStatus, t)}</span>
                    );
                  })()}
                  <span className="text-xs text-gray-500 font-mono">{attackCase.variant_count}v</span>
                  {expandedCases.has(attackCase.id) ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                </button>
                {expandedCases.has(attackCase.id) && (
                  <div className="px-4 pb-4 space-y-4 text-sm">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200">
                      {attackCase.quartet_present ? t("results.quartetPresent") : t("results.quartetMissing")}
                      </span>
                      {attackCase.control_assessment && (
                        <span className={`inline-flex px-2 py-0.5 rounded text-[11px] ${controlClasses(attackCase.control_assessment)}`}>{controlLabel(attackCase.control_assessment, t)}</span>
                      )}
                      {attackCase.business_verification_status && attackCase.business_verification_status !== "not_applicable" && (
                        <span className={`inline-flex px-2 py-0.5 rounded text-[11px] ${businessVerificationClasses(attackCase.business_verification_status)}`}>
                          {businessVerificationLabel(attackCase.business_verification_status, t)}
                        </span>
                      )}
                      {probeCountLabel(attackCase.probe_summary) && (
                        <span className="text-[11px] text-slate-500">{probeCountLabel(attackCase.probe_summary)}</span>
                      )}
                    </div>
                    {attackCase.control_summary && (
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
                        <p className="text-xs text-slate-500 font-semibold">{t("results.controlSummaryLabel")}</p>
                        <p className="text-slate-800">{attackCase.control_summary}</p>
                      </div>
                    )}
                    {attackCase.verdict_reason && (
                      <div>
                        <p className="text-xs text-slate-500 font-semibold mb-1">{t("results.verdictReasonLabel")}</p>
                        <p className="text-gray-700">{attackCase.verdict_reason}</p>
                      </div>
                    )}
                    {(probeFailureReason(attackCase.probe_summary) || (attackCase.probe_evidence_preview?.length ?? 0) > 0) && (
                      <div className="rounded-lg border border-fuchsia-100 bg-fuchsia-50/70 p-3 space-y-2">
                        <p className="text-xs text-fuchsia-700 uppercase tracking-wide font-semibold">{t("results.businessVerificationSection")}</p>
                        {probeFailureReason(attackCase.probe_summary) && (
                          <p className="text-sm text-slate-700">{probeFailureReason(attackCase.probe_summary)}</p>
                        )}
                        {(attackCase.probe_evidence_preview?.length ?? 0) > 0 && (
                          <div className="flex items-center gap-2 flex-wrap">
                            {attackCase.probe_evidence_preview?.map((entry, index) => (
                              <span
                                key={`${attackCase.id}-preview-${index}`}
                                className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200"
                              >
                                {typeof entry["kind"] === "string" ? entry["kind"] : "evidence"}
                                {typeof entry["step"] === "string" ? ` @ ${entry["step"]}` : ""}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                    {attackCase.legacy_attack_result_id && (attackCase.primary_attack_successful || resolvedCaseVerdictStatus(attackCase) === "manual_verified" || resolvedCaseVerdictStatus(attackCase) === "false_positive") && (
                      <div className="flex gap-2 flex-wrap">
                        <button type="button" disabled={reviewingId === attackCase.legacy_attack_result_id} onClick={() => handleReviewAction(attackCase.legacy_attack_result_id!, "manual_verified")} className="px-3 py-1.5 text-xs rounded-lg border border-teal-200 bg-teal-50 text-teal-700 hover:bg-teal-100 disabled:opacity-50">{t("results.markVerified")}</button>
                        <button type="button" disabled={reviewingId === attackCase.legacy_attack_result_id} onClick={() => handleReviewAction(attackCase.legacy_attack_result_id!, "false_positive")} className="px-3 py-1.5 text-xs rounded-lg border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 disabled:opacity-50">{t("results.markFalsePositive")}</button>
                        <button type="button" disabled={reviewingId === attackCase.legacy_attack_result_id} onClick={() => handleReviewAction(attackCase.legacy_attack_result_id!, "reset")} className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 bg-gray-50 text-gray-700 hover:bg-gray-100 disabled:opacity-50">{t("results.resetVerdict")}</button>
                      </div>
                    )}
                    {renderCaseDetail(caseDetails[attackCase.id], caseDetailLoading.has(attackCase.id), caseDetailErrors[attackCase.id], t)}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="card divide-y divide-gray-100">
          {filteredResults.length === 0 ? (
            <div className="p-8 text-center text-gray-500">{t("results.noLegacy")}</div>
          ) : (
            filteredResults.map((result) => {
              const risk = result.risk_level as RiskLevel;
              const colors = riskColors[risk];
              const controlVariants = Array.isArray(result.analysis_raw?.["control_variants"]) ? (result.analysis_raw?.["control_variants"] as Array<Record<string, unknown>>) : [];
              const attackGoalScore = typeof result.analysis_raw?.["attack_goal_score"] === "number" ? Number(result.analysis_raw["attack_goal_score"]) : result.attack_goal_score;
              const utilityScore = typeof result.analysis_raw?.["utility_score"] === "number" ? Number(result.analysis_raw["utility_score"]) : result.utility_score;
              const advancedTrace = result.analysis_raw ? JSON.stringify(result.analysis_raw, null, 2) : null;
              const responseEvaluation = resolveResponseEvaluation(result);
              return (
                <div key={result.id}>
                  <button onClick={() => toggleLegacy(result.id)} className="w-full flex items-center gap-3 p-4 text-left hover:bg-gray-50 transition-colors">
                    {result.attack_successful ? <XCircle className="w-4 h-4 text-red-500 shrink-0" /> : <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-900 truncate">{result.attack_name}</p>
                      <p className="text-xs text-gray-500">{result.technique} · {result.template_id}</p>
                    </div>
                    {result.case_final_outcome
                      && result.case_final_outcome !== "passed"
                      && result.case_final_outcome !== "not_evaluable" && (
                      <span className={`text-[11px] px-2 py-0.5 rounded ${controlClasses(result.case_final_outcome)}`}>{controlLabel(result.case_final_outcome, t)}</span>
                    )}
                    {result.business_verification_status && result.business_verification_status !== "not_applicable" && (
                      <span className={`text-[11px] px-2 py-0.5 rounded ${businessVerificationClasses(result.business_verification_status)}`}>
                        {businessVerificationLabel(result.business_verification_status, t)}
                      </span>
                    )}
                    <span className={`text-xs px-2 py-0.5 rounded ${colors.bg} ${colors.text}`}>{risk.toUpperCase()}</span>
                    {(() => {
                      const _vStatus = resolvedVerdictStatus(result);
                      if (_vStatus === "not_evaluable") {
                        const _cat = notEvaluableDisplayCategory(responseEvaluation);
                        if (_cat) return <NotEvaluablePills category={_cat} t={t} />;
                      }
                      return (
                        <span className={`text-[11px] px-2 py-0.5 rounded ${verdictClasses(_vStatus)}`}>{verdictLabel(_vStatus, t)}</span>
                      );
                    })()}
                    {expandedLegacy.has(result.id) ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                  </button>
                  {expandedLegacy.has(result.id) && (
                    <div className="px-4 pb-4 space-y-4 text-sm">
                      <div className="flex items-center gap-2 flex-wrap">
                        {result.case_id && (
                          <button
                            type="button"
                            onClick={() => {
                              setViewMode("cases");
                              setExpandedCases((prev) => new Set(prev).add(result.case_id!));
                              void ensureCaseDetail(result.case_id!);
                            }}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100"
                          >
                            <Shield className="w-3 h-3" />
                            {t("results.openLinkedCase")}
                          </button>
                        )}
                        {result.quartet_present != null && (
                          <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200">
                        {result.quartet_present ? t("results.quartetPresent") : t("results.quartetMissing")}
                          </span>
                        )}
                        <span className={`inline-flex px-2 py-0.5 rounded text-[11px] ${businessVerificationClasses(result.business_verification_status)}`}>
                          {businessVerificationLabel(result.business_verification_status, t)}
                        </span>
                        {probeCountLabel(result.probe_summary) && (
                          <span className="text-[11px] text-slate-500">{probeCountLabel(result.probe_summary)}</span>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <pre className="bg-gray-50 border border-gray-100 p-3 rounded-lg text-gray-800 font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-60 overflow-y-auto">{result.payload_text}</pre>
                        <pre className="bg-gray-50 border border-gray-100 p-3 rounded-lg text-gray-800 font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-60 overflow-y-auto">{resolvedTargetResponse(result) || "(no response)"}</pre>
                      </div>
                      <ResponseEvaluationPanel evaluation={responseEvaluation} t={t} />
                      {result.evidence && <p className="text-gray-700">{result.evidence}</p>}
                      {(result.control_assessment || result.control_summary) && (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                          <p className="text-sm text-slate-800">
                            {result.control_assessment && <span className={`inline-flex mr-2 px-2 py-0.5 rounded text-[11px] ${controlClasses(result.control_assessment)}`}>{controlLabel(result.control_assessment, t)}</span>}
                            {result.control_summary || t("results.noControlSummary")}
                          </p>
                        </div>
                      )}
                      {(attackGoalScore != null || utilityScore != null) && (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 flex items-center gap-4 flex-wrap text-sm">
                          <span>{t("report.attackGoalScore")}: <span className={`font-mono font-semibold ${scoreTone(attackGoalScore)}`}>{attackGoalScore != null ? attackGoalScore.toFixed(2) : "-"}</span></span>
                          <span>{t("report.utilityScore")}: <span className={`font-mono font-semibold ${utilityScore == null ? "text-gray-500" : utilityScore >= 0.8 ? "text-emerald-700" : utilityScore >= 0.5 ? "text-amber-700" : "text-rose-700"}`}>{utilityScore != null ? utilityScore.toFixed(2) : "-"}</span></span>
                        </div>
                      )}
                      {(probeFailureReason(result.probe_summary) || (result.probe_evidence_preview?.length ?? 0) > 0) && (
                        <div className="rounded-lg border border-fuchsia-100 bg-fuchsia-50/70 p-3 space-y-2">
                          <p className="text-xs text-fuchsia-700 uppercase tracking-wide font-semibold">{t("results.businessVerificationSection")}</p>
                          {probeFailureType(result.probe_summary) && (
                            <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200 font-mono">
                              {probeFailureType(result.probe_summary)}
                            </span>
                          )}
                          {probeFailureReason(result.probe_summary) && (
                            <p className="text-sm text-slate-700">{probeFailureReason(result.probe_summary)}</p>
                          )}
                          {(result.probe_evidence_preview?.length ?? 0) > 0 && (
                            <div className="flex items-center gap-2 flex-wrap">
                              {result.probe_evidence_preview?.map((entry, index) => (
                                <span
                                  key={`${result.id}-probe-${index}`}
                                  className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200"
                                >
                                  {typeof entry["kind"] === "string" ? entry["kind"] : "evidence"}
                                  {typeof entry["step"] === "string" ? ` @ ${entry["step"]}` : ""}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                      {(result.attack_successful || resolvedVerdictStatus(result) === "manual_verified" || resolvedVerdictStatus(result) === "false_positive") && (
                        <div className="flex gap-2 flex-wrap">
                          <button type="button" disabled={reviewingId === result.id} onClick={() => handleReviewAction(result.id, "manual_verified")} className="px-3 py-1.5 text-xs rounded-lg border border-teal-200 bg-teal-50 text-teal-700 hover:bg-teal-100 disabled:opacity-50">{t("results.markVerified")}</button>
                          <button type="button" disabled={reviewingId === result.id} onClick={() => handleReviewAction(result.id, "false_positive")} className="px-3 py-1.5 text-xs rounded-lg border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 disabled:opacity-50">{t("results.markFalsePositive")}</button>
                          <button type="button" disabled={reviewingId === result.id} onClick={() => handleReviewAction(result.id, "reset")} className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 bg-gray-50 text-gray-700 hover:bg-gray-100 disabled:opacity-50">{t("results.resetVerdict")}</button>
                        </div>
                      )}
                      {controlVariants.length > 0 && (
                        <div className="space-y-3">
                          {controlVariants.map((variant, index) => (
                            <div key={`${result.id}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
                              <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200">
                                {typeof variant["variant"] === "string" ? variant["variant"] : `control-${index + 1}`}
                              </span>
                              <pre className="bg-white border border-slate-200 p-3 rounded-lg text-slate-800 font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">{typeof variant["prompt"] === "string" ? variant["prompt"] : ""}</pre>
                              <pre className="bg-white border border-slate-200 p-3 rounded-lg text-slate-800 font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">{typeof variant["response"] === "string" ? variant["response"] : "(no response)"}</pre>
                            </div>
                          ))}
                        </div>
                      )}
                      {advancedTrace && (
                        <pre className="bg-slate-50 border border-slate-200 p-3 rounded-lg text-slate-800 font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-80 overflow-y-auto">
                          {advancedTrace}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
