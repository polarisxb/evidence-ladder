import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { Shield, AlertTriangle, ChevronDown, ChevronUp, Download, Loader2 } from "lucide-react";
import { createAutoTestRetestDraft, getAutoTestSummary } from "../api/autotest";
import { getCaseDetail } from "../api/cases";
import { ResponseEvaluationPanel } from "../components/ResponseEvaluationPanel";
import { ResultSemanticsCard } from "../components/ResultSemanticsCard";
import { CanaryJourney } from "../components/CanaryJourney";
import { downloadReport, getReport } from "../api/reports";
import { createScan } from "../api/scans";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";
import { CategoryRadarChart } from "../components/charts/CategoryRadarChart";
import { CompliancePanel } from "../components/CompliancePanel";
import { resolveResponseEvaluation } from "../utils/responseEvaluation";
import { riskColors, riskLabel } from "../utils/risk";
import type { AttackCaseDetail, AutoTestRetestOutcome, AutoTestSummary, SecurityReport, RiskLevel } from "../types";

function verdictLabel(status?: string | null, t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  switch (status) {
    case "rule_verified": return _t("common.ruleVerified");
    case "manual_verified": return _t("common.manualVerified");
    case "ai_suspected": return _t("common.aiSuspected");
    case "manual_review_needed": return _t("common.manualReviewNeeded");
    case "false_positive": return _t("common.falsePositive");
    case "passed": return _t("common.passed");
    case "not_evaluable": return _t("common.notEvaluable");
    default: return status || "—";
  }
}

function verdictClasses(status?: string | null) {
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

function outcomeLabel(outcome?: string | null, t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  switch (outcome) {
    case "FULL_INJECTION_SUCCESS": return _t("report.fullSuccess");
    case "PARTIAL_INJECTION_SUCCESS": return _t("report.partialSuccess");
    case "ATTACK_DISCUSSION_ONLY": return _t("report.discussionOnly");
    case "NO_INJECTION_SUCCESS": return _t("report.noSuccess");
    default: return _t("common.unclassified");
  }
}

function outcomeClasses(outcome?: string | null) {
  switch (outcome) {
    case "FULL_INJECTION_SUCCESS":
      return "bg-red-50 text-red-700 border border-red-200";
    case "PARTIAL_INJECTION_SUCCESS":
      return "bg-orange-50 text-orange-700 border border-orange-200";
    case "ATTACK_DISCUSSION_ONLY":
      return "bg-sky-50 text-sky-700 border border-sky-200";
    case "NO_INJECTION_SUCCESS":
      return "bg-gray-100 text-gray-600 border border-gray-200";
    default:
      return "bg-gray-100 text-gray-500 border border-gray-200";
  }
}

function executionModeLabel(mode?: string | null, t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  switch (mode) {
    case "DISCUSSING_ATTACK": return _t("common.discussingAttack");
    case "EXECUTING_ATTACK": return _t("common.executingAttack");
    case "UNCERTAIN": return _t("common.uncertain");
    default: return _t("common.notClassified");
  }
}

function behaviorPills(flags?: Record<string, unknown> | null, t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  if (!flags || typeof flags !== "object") return [];
  const pills: Array<{ label: string; tone: string }> = [];
  if (flags.discussion_only === true) pills.push({ label: _t("common.discussionOnly"), tone: "bg-sky-50 text-sky-700 border border-sky-200" });
  if (flags.attack_obedience === true) pills.push({ label: _t("common.attackObedience"), tone: "bg-orange-50 text-orange-700 border border-orange-200" });
  if (flags.task_deviation === true) pills.push({ label: _t("common.taskDeviation"), tone: "bg-amber-50 text-amber-800 border border-amber-200" });
  if (flags.secret_disclosure === true) pills.push({ label: _t("common.secretDisclosure"), tone: "bg-red-50 text-red-700 border border-red-200" });
  if (flags.unauthorized_action_claim === true) pills.push({ label: _t("common.unauthorizedActionClaim"), tone: "bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200" });
  if (flags.original_task_completed === true) pills.push({ label: _t("common.originalTaskCompleted"), tone: "bg-emerald-50 text-emerald-700 border border-emerald-200" });
  if (flags.original_task_completed === false) pills.push({ label: _t("common.originalTaskNotCompleted"), tone: "bg-slate-100 text-slate-700 border border-slate-200" });
  return pills;
}

function controlAssessmentLabel(assessment?: string | null, t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  switch (assessment) {
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

function controlAssessmentClasses(assessment?: string | null) {
  switch (assessment) {
    case "rule_verified_finding":
      return "bg-emerald-50 text-emerald-700 border border-emerald-200";
    case "attack_delta_supported":
      return "bg-emerald-50 text-emerald-700 border border-emerald-200";
    case "discussion_supported":
      return "bg-sky-50 text-sky-700 border border-sky-200";
    case "controls_inconclusive":
      return "bg-amber-50 text-amber-800 border border-amber-200";
    case "controls_missing":
      return "bg-gray-100 text-gray-600 border border-gray-200";
    default:
      return "bg-gray-100 text-gray-600 border border-gray-200";
  }
}

function variantLabel(variantType?: string | null, t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  switch (variantType) {
    case "attack": return _t("common.attack");
    case "clean": return _t("common.clean");
    case "quoted_attack": return _t("common.quotedAttack");
    case "benign_distractor": return _t("common.benignDistractor");
    default: return variantType || "Variant";
  }
}

function variantClasses(variantType?: string | null) {
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

function scoreTone(score: number | null | undefined) {
  if (score == null) return "text-gray-500";
  if (score >= 0.8) return "text-red-600";
  if (score >= 0.5) return "text-orange-600";
  if (score >= 0.2) return "text-amber-700";
  return "text-green-600";
}

function formatRate(value: number | null | undefined) {
  return value == null ? "-" : `${(value * 100).toFixed(1)}%`;
}

function evidenceTone(level?: string | null) {
  switch (level) {
    case "E5":
    case "E4":
    case "E3":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "E2":
    case "E1":
      return "border-amber-200 bg-amber-50 text-amber-800";
    case "E0":
      return "border-orange-200 bg-orange-50 text-orange-900";
    default:
      return "border-gray-200 bg-gray-100 text-gray-600";
  }
}

function retestOutcomeLabel(outcome: AutoTestRetestOutcome, t: (k: string) => string) {
  switch (outcome) {
    case "confirmed_by_retest":
      return t("autotestSummary.confirmedByRetest");
    case "overturned_by_retest":
      return t("autotestSummary.overturnedByRetest");
    case "manual_review_needed":
      return t("autotestSummary.manualReviewNeeded");
    default:
      return outcome;
  }
}

function retestOutcomeClasses(outcome: AutoTestRetestOutcome) {
  switch (outcome) {
    case "confirmed_by_retest":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "overturned_by_retest":
      return "border-rose-200 bg-rose-50 text-rose-700";
    case "manual_review_needed":
      return "border-amber-200 bg-amber-50 text-amber-800";
    default:
      return "border-gray-200 bg-gray-100 text-gray-600";
  }
}

function AutoTestSummaryPanel({
  summary,
  retestStarting,
  onStartRetest,
  t,
}: {
  summary: AutoTestSummary;
  retestStarting: boolean;
  onStartRetest: () => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  const metrics = summary.metrics;
  const evidenceCounts = summary.items.reduce<Record<string, number>>((acc, item) => {
    const level = item.evidence_level ?? "none";
    acc[level] = (acc[level] ?? 0) + 1;
    return acc;
  }, {});
  const retestComparisons = summary.retest_comparisons ?? [];
  const retestCounts = summary.retest_outcome_counts ?? {};
  const retestOutcomes: AutoTestRetestOutcome[] = [
    "confirmed_by_retest",
    "overturned_by_retest",
    "manual_review_needed",
  ];

  return (
    <section className="card p-6 space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-gray-900">{t("autotestSummary.title")}</h2>
          <p className="mt-1 text-sm text-gray-500">{t("autotestSummary.desc")}</p>
        </div>
        <div className="flex items-center gap-2">
          {summary.retest_actions.length > 0 ? (
            <button
              type="button"
              onClick={onStartRetest}
              disabled={retestStarting}
              className="inline-flex items-center gap-2 rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {retestStarting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {t("autotestSummary.startRetest")}
            </button>
          ) : null}
          <span className="rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-600">
            {summary.scan_status}
          </span>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        {[
          [t("autotestSummary.evidenceAsr"), formatRate(metrics.evidence_verified_asr)],
          [t("autotestSummary.rawAsr"), formatRate(metrics.raw_asr)],
          [t("autotestSummary.notEvaluable"), formatRate(metrics.not_evaluable_rate)],
          [t("autotestSummary.retestActions"), String(summary.retest_actions.length)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-gray-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</p>
            <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            {t("autotestSummary.evidenceDistribution")}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {["E0", "E1", "E2", "E3", "E4", "E5"].map((level) => (
              <span
                key={level}
                className={`inline-flex items-center rounded-lg border px-2.5 py-1 text-xs font-semibold ${evidenceTone(level)}`}
              >
                {level}: {evidenceCounts[level] ?? 0}
              </span>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            {t("autotestSummary.retestQueue")}
          </p>
          {summary.retest_actions.length > 0 ? (
            <div className="mt-3 space-y-2">
              {summary.retest_actions.slice(0, 3).map((group) => (
                <div key={group.result_id} className="rounded-lg bg-gray-50 px-3 py-2">
                  <p className="truncate text-sm font-medium text-gray-800">{group.attack_name}</p>
                  <p className="mt-1 text-xs text-gray-500">
                    {group.actions.map((action) => action.action_type).join(", ")}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm text-gray-400">{t("autotestSummary.noRetest")}</p>
          )}
        </div>
      </div>

      {summary.retest_source && (
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">
                {t("autotestSummary.retestRelation")}
              </p>
              <p className="mt-1 text-sm text-indigo-950">
                {t("autotestSummary.sourceScan")}:{" "}
                <span className="font-mono text-xs">{summary.retest_source.source_scan_id}</span>
              </p>
              {summary.retest_run && (
                <p className="mt-1 text-sm text-indigo-950">
                  {t("autotestSummary.retestRun")}:{" "}
                  <span className="font-mono text-xs">{summary.retest_run.id}</span>
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {summary.retest_run && (
                <>
                  <span className="max-w-full break-all rounded-lg border border-indigo-200 bg-white px-2.5 py-1 text-xs font-medium text-indigo-700">
                    {t("autotestSummary.retestScan")}: {summary.retest_run.retest_scan_id}
                  </span>
                  <span className="rounded-lg border border-indigo-200 bg-white px-2.5 py-1 text-xs font-medium text-indigo-700">
                    {t("autotestSummary.runStatus")}: {summary.retest_run.status}
                  </span>
                </>
              )}
              <span className="rounded-lg border border-indigo-200 bg-white px-2.5 py-1 text-xs font-medium text-indigo-700">
                {summary.retest_source.retest_type ?? "retest"}
              </span>
              <span className="rounded-lg border border-indigo-200 bg-white px-2.5 py-1 text-xs font-medium text-indigo-700">
                {summary.retest_source.retest_reason}
              </span>
              <span className="rounded-lg border border-indigo-200 bg-white px-2.5 py-1 text-xs font-medium text-indigo-700">
                {summary.retest_source.source_result_ids.length} {t("autotestSummary.sourceFindings")}
              </span>
            </div>
          </div>
        </div>
      )}

      {retestComparisons.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t("autotestSummary.retestOutcomes")}
            </p>
            <div className="flex flex-wrap gap-2">
              {retestOutcomes.map((outcome) => (
                <span
                  key={outcome}
                  className={`inline-flex items-center rounded-lg border px-2.5 py-1 text-xs font-semibold ${retestOutcomeClasses(outcome)}`}
                >
                  {retestOutcomeLabel(outcome, t)}: {retestCounts[outcome] ?? 0}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-3 space-y-2">
            {retestComparisons.slice(0, 6).map((comparison) => (
              <div key={comparison.source_result_id} className="rounded-lg bg-gray-50 px-3 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="min-w-0 flex-1 truncate text-sm font-medium text-gray-800">
                    {comparison.source_attack_name}
                  </p>
                  <span className={`inline-flex rounded-lg border px-2 py-0.5 text-[11px] font-semibold ${retestOutcomeClasses(comparison.outcome)}`}>
                    {retestOutcomeLabel(comparison.outcome, t)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  {comparison.source_category}
                  {comparison.source_evidence_level ? ` | ${comparison.source_evidence_level}` : ""}
                  {comparison.retest_evidence_levels.length > 0
                    ? ` -> ${comparison.retest_evidence_levels.join(", ")}`
                    : ""}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function businessVerificationLabel(status?: string | null, t?: (k: string) => string) {
  const _t = t ?? ((k: string) => k);
  switch (status) {
    case "text_claim_only": return _t("common.textClaimOnly");
    case "probe_verified": return _t("common.probeVerified");
    case "probe_failed": return _t("common.probeFailed");
    case "probe_inconclusive": return _t("common.probeInconclusive");
    default: return _t("common.notApplicable");
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

function probeFailureType(probeSummary?: Record<string, unknown> | null) {
  return typeof probeSummary?.["failure_type"] === "string" ? probeSummary["failure_type"] : null;
}

function probeFailureReason(probeSummary?: Record<string, unknown> | null) {
  return typeof probeSummary?.["failure_reason"] === "string" ? probeSummary["failure_reason"] : null;
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

export function Report() {
  const navigate = useNavigate();
  const { scanId } = useParams<{ scanId: string }>();
  const [report, setReport] = useState<SecurityReport | null>(null);
  const [autotestSummary, setAutotestSummary] = useState<AutoTestSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [retestStarting, setRetestStarting] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [caseDetails, setCaseDetails] = useState<Record<string, AttackCaseDetail>>({});
  const [caseDetailErrors, setCaseDetailErrors] = useState<Record<string, string>>({});
  const [caseDetailLoading, setCaseDetailLoading] = useState<Set<string>>(new Set());
  const { toast } = useToast();
  const { t } = useLocale();

  useEffect(() => {
    if (!scanId) return;
    Promise.all([
      getReport(scanId),
      getAutoTestSummary(scanId).catch(() => null),
    ])
      .then(([nextReport, nextSummary]) => {
        setReport(nextReport);
        setAutotestSummary(nextSummary);
      })
      .catch((err) => toast("error", `${t("report.failedToLoad")}: ${err.message}`))
      .finally(() => setLoading(false));
  }, [scanId]);

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
      setCaseDetailErrors((prev) => ({
        ...prev,
        [caseId]: err instanceof Error ? err.message : String(err),
      }));
    } finally {
      setCaseDetailLoading((prev) => {
        const next = new Set(prev);
        next.delete(caseId);
        return next;
      });
    }
  }

  function toggleExpand(id: string, caseId?: string | null) {
    const isOpen = expanded.has(id);
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    if (!isOpen && caseId) {
      void ensureCaseDetail(caseId);
    }
  }

  async function handleExport(format: "json" | "html") {
    if (!scanId) return;
    try {
      await downloadReport(scanId, format);
    } catch (err) {
      toast("error", `${t("report.failedToExport")}: ${err instanceof Error ? err.message : err}`);
    }
  }

  async function handleStartRetest() {
    if (!scanId) return;
    setRetestStarting(true);
    try {
      const draft = await createAutoTestRetestDraft(scanId);
      const { task_id } = await createScan(draft.scan_config);
      toast("success", t("autotestSummary.retestStarted"));
      navigate(`/scan/${task_id}`);
    } catch (err) {
      toast("error", `${t("autotestSummary.retestFailed")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setRetestStarting(false);
    }
  }

  if (loading) return <div className="text-center text-gray-500 py-12">{t("common.loading")}</div>;
  if (!report || !scanId) return <div className="text-center text-gray-500 py-12">{t("common.noData")}</div>;

  const risk = report.risk_level as RiskLevel;
  const colors = riskColors[risk];
  const postureScore = report.security_posture_score ?? report.overall_score;
  const isPartial = report.completed_attacks < report.total_attacks;
  const findingBreakdown = report.finding_breakdown ?? {
    rule_verified: 0,
    manual_verified: 0,
    ai_suspected: 0,
    manual_review_needed: 0,
    false_positive: 0,
    not_evaluable: 0,
  };
  const blackboxOutcomeBreakdown = report.blackbox_outcome_breakdown ?? {
    full_injection_success: 0,
    partial_injection_success: 0,
    attack_discussion_only: 0,
    no_injection_success: 0,
    unclassified: 0,
  };
  const businessVerificationBreakdown = report.business_verification_breakdown ?? null;
  // Verdict-based three-way headline: Confirmed / Needs Review / False Positive.
  // When older reports don't carry the new `finding_counts` fields we fall back
  // to deriving the numbers from `finding_breakdown` so the card still renders.
  const confirmedFindings =
    report.confirmed_findings ??
    findingBreakdown.rule_verified +
      findingBreakdown.manual_verified +
      findingBreakdown.ai_suspected;
  const needsReviewCount =
    report.needs_review_count ?? findingBreakdown.manual_review_needed;
  const falsePositiveCount =
    report.false_positive_count ?? findingBreakdown.false_positive;
  const notEvaluableCount =
    report.finding_counts?.not_evaluable ?? findingBreakdown.not_evaluable;
  // ``finding_counts.passed`` is only populated on reports generated after
  // Phase A. Older reports leave it blank, but we can always recompute it
  // from the total — the other five buckets cover every non-passed verdict,
  // so whatever is left must be ``passed``.
  const passedCount =
    report.finding_counts?.passed ??
    Math.max(
      0,
      report.total_attacks -
        confirmedFindings -
        needsReviewCount -
        falsePositiveCount -
        notEvaluableCount,
    );
  const categoryScores = report.category_scores ?? [];
  const criticalFindings = report.critical_findings ?? [];
  const highFindings = report.high_findings ?? [];
  const mediumFindings = report.medium_findings ?? [];
  const lowFindings = report.low_findings ?? [];
  const recommendations = report.recommendations ?? [];
  const utilityScoredResults = report.utility_scored_results ?? 0;

  const allFindings = [
    ...criticalFindings.map((f) => ({ ...f, level: "critical" as RiskLevel })),
    ...highFindings.map((f) => ({ ...f, level: "high" as RiskLevel })),
    ...mediumFindings.map((f) => ({ ...f, level: "medium" as RiskLevel })),
    ...lowFindings.map((f) => ({ ...f, level: "low" as RiskLevel })),
  ];

  const exportBtn =
    "flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white border border-gray-200 hover:border-gray-400 text-gray-700 rounded-lg transition-colors shadow-sm";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">{t("report.title")}</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500 font-mono">{report.scan_name}</span>
          <button type="button" onClick={() => void handleExport("json")} className={exportBtn}>
            <Download className="w-3.5 h-3.5" />
            JSON
          </button>
          <button type="button" onClick={() => void handleExport("html")} className={exportBtn}>
            <Download className="w-3.5 h-3.5" />
            HTML
          </button>
        </div>
      </div>

      {isPartial && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      {t("report.partialReport", { completed: report.completed_attacks, total: report.total_attacks })}
        </div>
      )}

      {report.target_health && (
        <div className={`rounded-xl border px-5 py-4 space-y-2 ${
          report.target_health === "healthy"
            ? "border-emerald-200 bg-emerald-50"
            : report.target_health === "degraded"
            ? "border-amber-200 bg-amber-50"
            : "border-rose-200 bg-rose-50"
        }`}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-900">{t("report.targetHealthTitle")}</h3>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              report.target_health === "healthy"
                ? "bg-emerald-100 text-emerald-700"
                : report.target_health === "degraded"
                ? "bg-amber-100 text-amber-800"
                : "bg-rose-100 text-rose-700"
            }`}>
              {report.target_health}
            </span>
          </div>
          <p className="text-xs text-gray-500">{t("report.targetHealthDesc")}</p>
          <div className="grid grid-cols-3 gap-4 text-xs pt-1">
            <div>
              <span className="text-gray-500">{t("report.healthProbe")}:</span>{" "}
              <span className="font-medium">
                {report.health_probe_passed === true
                  ? t("report.healthProbePassed")
                  : report.health_probe_passed === false
                  ? t("report.healthProbeFailed")
                  : t("report.healthProbeNA")}
              </span>
            </div>
            {report.invalid_response_ratio != null && (
              <div>
                <span className="text-gray-500">{t("report.invalidRatio")}:</span>{" "}
                <span className="font-mono font-medium">{(report.invalid_response_ratio * 100).toFixed(1)}%</span>
              </div>
            )}
            {report.recent_health_signature && (
              <div className="truncate" title={report.recent_health_signature}>
                <span className="text-gray-500">{t("report.healthSignature")}:</span>{" "}
                <span className="font-mono">{report.recent_health_signature}</span>
              </div>
            )}
          </div>
          {report.health_failure_reason && (
            <p className="text-xs text-gray-700 pt-1">
              <span className="text-gray-500">{t("report.healthReason")}:</span> {report.health_failure_reason}
            </p>
          )}
          {report.target_health === "unhealthy" && isPartial && (
            <p className="text-xs font-medium text-rose-700 pt-1">
              <AlertTriangle className="w-3.5 h-3.5 inline-block mr-1 -mt-0.5" />
              {t("report.healthAborted")}
            </p>
          )}
        </div>
      )}

      {autotestSummary && (
        <AutoTestSummaryPanel
          summary={autotestSummary}
          retestStarting={retestStarting}
          onStartRetest={() => void handleStartRetest()}
          t={t}
        />
      )}

      <div className="grid grid-cols-4 gap-4">
        <div className={`col-span-1 rounded-xl p-6 border ${colors.border} ${colors.bg} flex flex-col items-center justify-center`}>
          <p className="text-4xl font-bold text-gray-900">{postureScore}</p>
          <p className={`text-sm font-mono mt-1 ${colors.text}`}>{riskLabel(risk)}</p>
          <p className="text-[11px] text-gray-500 mt-2">{t("report.overallScore")}</p>
        </div>
        <div className="col-span-3 card p-6">
          <div className="grid grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {report.completed_attacks}/{report.total_attacks}
              </p>
              <p className="text-xs text-gray-500">{isPartial ? t("scanProgress.completed") + " / " + t("common.all") : t("report.totalTests")}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-orange-600">{report.successful_attacks}</p>
              <p className="text-xs text-gray-500">{t("report.successfulAttacks")}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{report.attack_success_rate}%</p>
              <p className="text-xs text-gray-500">{t("report.attackSuccessRate")}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {report.average_finding_severity != null ? report.average_finding_severity.toFixed(1) : "-"}
              </p>
              <p className="text-xs text-gray-500">{t("report.avgFindingSeverity")}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 text-center mt-4 pt-4 border-t border-gray-100">
            <div>
              <p className={`text-2xl font-bold ${scoreTone(report.average_attack_goal_score)}`}>
                {report.average_attack_goal_score != null ? report.average_attack_goal_score.toFixed(2) : "-"}
              </p>
              <p className="text-xs text-gray-500">{t("report.avgAttackGoalScore")}</p>
            </div>
            <div>
              <p className={`text-2xl font-bold ${report.average_utility_score == null ? "text-gray-500" : report.average_utility_score >= 0.8 ? "text-emerald-700" : report.average_utility_score >= 0.5 ? "text-amber-700" : "text-rose-700"}`}>
                {report.average_utility_score != null ? report.average_utility_score.toFixed(2) : "-"}
              </p>
              <p className="text-xs text-gray-500">{t("report.avgUtilityScore", { n: utilityScoredResults })}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="card p-6">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900">{t("report.coreBreakdown")}</h2>
          <p className="text-xs text-gray-500 mt-1 max-w-3xl">{t("report.coreBreakdownHint")}</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Each card deep-links into ScanResults with a preselected verdict
              filter: clicking the headline number is the fastest way to
              triage cases inside the matching bucket. The `verdict=confirmed`
              composite mirrors the Report "Confirmed Findings" card =
              rule_verified + manual_verified + ai_suspected. */}
          <Link
            to={`/results/${scanId}?verdict=confirmed`}
            className="block rounded-xl border border-orange-200 bg-orange-50 p-5 transition-all hover:shadow-md hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-orange-300"
          >
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-orange-700">
                {t("report.confirmedFindings")}
              </p>
              <AlertTriangle className="w-4 h-4 text-orange-600" />
            </div>
            <p className="text-4xl font-bold text-orange-700 mt-2">{confirmedFindings}</p>
            <p className="text-[11px] text-orange-800/80 mt-2 leading-snug">
              {t("report.confirmedFindingsDesc")}
            </p>
          </Link>
          <Link
            to={`/results/${scanId}?verdict=manual_review_needed`}
            className="block rounded-xl border border-slate-200 bg-slate-50 p-5 transition-all hover:shadow-md hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-slate-300"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">
              {t("report.needsReviewCount")}
            </p>
            <p className="text-4xl font-bold text-slate-700 mt-2">{needsReviewCount}</p>
            <p className="text-[11px] text-slate-600 mt-2 leading-snug">
              {t("report.needsReviewCountDesc")}
            </p>
          </Link>
          <Link
            to={`/results/${scanId}?verdict=false_positive`}
            className="block rounded-xl border border-rose-200 bg-rose-50 p-5 transition-all hover:shadow-md hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-rose-300"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-rose-700">
              {t("report.falsePositiveCount")}
            </p>
            <p className="text-4xl font-bold text-rose-700 mt-2">{falsePositiveCount}</p>
            <p className="text-[11px] text-rose-700/80 mt-2 leading-snug">
              {t("report.falsePositiveCountDesc")}
            </p>
          </Link>
        </div>
        {/* Five-bucket reconciliation row: makes the headline three-way split
            add up to total_attacks when you include Passed and Not Evaluable,
            matching the finding-split row in the HTML export. */}
        <div className="mt-5 pt-4 border-t border-gray-100 text-xs text-gray-600 text-center">
          <span className="font-semibold text-gray-900">{report.total_attacks}</span>{" "}
          {t("report.postureBreakdownTotalLabel")}
          <span className="mx-2 text-gray-400">=</span>
          <span className="inline-flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
            <span>
              <span className="font-semibold text-orange-700">{confirmedFindings}</span>{" "}
              {t("report.postureBreakdownConfirmed")}
            </span>
            <span className="text-gray-300">·</span>
            <span>
              <span className="font-semibold text-slate-700">{needsReviewCount}</span>{" "}
              {t("report.postureBreakdownNeedsReview")}
            </span>
            <span className="text-gray-300">·</span>
            <span>
              <span className="font-semibold text-rose-700">{falsePositiveCount}</span>{" "}
              {t("report.postureBreakdownFalsePositive")}
            </span>
            <span className="text-gray-300">·</span>
            <span>
              <span className="font-semibold text-emerald-700">{passedCount}</span>{" "}
              {t("report.postureBreakdownPassed")}
            </span>
            <span className="text-gray-300">·</span>
            <span>
              <span className="font-semibold text-amber-700">{notEvaluableCount}</span>{" "}
              {t("report.postureBreakdownNotEvaluable")}
            </span>
          </span>
        </div>
      </div>

      <ResultSemanticsCard t={t} />

      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("report.categoryPassRates")}</h2>
        <div className="space-y-3">
          {categoryScores.map((cs) => {
            const catRisk = cs.risk_level as RiskLevel;
            const catColors = riskColors[catRisk];
            return (
              <div key={cs.category} className="flex items-center gap-4">
                <span className="text-sm text-gray-700 w-48">{cs.category_name}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${cs.pass_rate >= 70 ? "bg-green-500" : cs.pass_rate >= 50 ? "bg-yellow-500" : "bg-red-500"}`}
                    style={{ width: `${cs.pass_rate}%` }}
                  />
                </div>
                <span className={`text-xs font-mono w-16 text-right ${catColors.text}`}>{cs.pass_rate}%</span>
                <span className="text-xs text-gray-500 w-28 text-right">
                  {cs.successful_attacks}/{cs.total_tests} {t("report.successful")}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">{t("report.categoryRadar")}</h2>
          <CategoryRadarChart scores={categoryScores} />
        </div>
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("report.findingTriage")}</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <p className="text-2xl font-bold text-emerald-700">{findingBreakdown.rule_verified}</p>
              <p className="text-xs text-emerald-800 mt-1">{t("common.ruleVerified")}</p>
            </div>
            <div className="rounded-xl border border-teal-200 bg-teal-50 p-4">
              <p className="text-2xl font-bold text-teal-700">{findingBreakdown.manual_verified}</p>
              <p className="text-xs text-teal-800 mt-1">{t("common.manualVerified")}</p>
            </div>
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-2xl font-bold text-amber-800">{findingBreakdown.ai_suspected}</p>
              <p className="text-xs text-amber-900 mt-1">{t("common.aiSuspected")}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-100 p-4">
              <p className="text-2xl font-bold text-slate-700">{findingBreakdown.manual_review_needed}</p>
              <p className="text-xs text-slate-800 mt-1">{t("common.manualReviewNeeded")}</p>
            </div>
            <div className="rounded-xl border border-orange-200 bg-orange-50 p-4">
              <p className="text-2xl font-bold text-orange-800">{findingBreakdown.not_evaluable ?? 0}</p>
              <p className="text-xs text-orange-900 mt-1">{t("common.notEvaluable")}</p>
            </div>
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
              <p className="text-2xl font-bold text-rose-700">{findingBreakdown.false_positive}</p>
              <p className="text-xs text-rose-800 mt-1">{t("common.falsePositive")}</p>
            </div>
          </div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("report.blackboxOutcomes")}</h2>
          <div className="grid grid-cols-5 gap-3 mb-6">
            <div className="rounded-xl border border-red-200 bg-red-50 p-4">
              <p className="text-2xl font-bold text-red-700">{blackboxOutcomeBreakdown.full_injection_success}</p>
              <p className="text-xs text-red-800 mt-1">{t("report.fullSuccess")}</p>
            </div>
            <div className="rounded-xl border border-orange-200 bg-orange-50 p-4">
              <p className="text-2xl font-bold text-orange-700">{blackboxOutcomeBreakdown.partial_injection_success}</p>
              <p className="text-xs text-orange-800 mt-1">{t("report.partialSuccess")}</p>
            </div>
            <div className="rounded-xl border border-sky-200 bg-sky-50 p-4">
              <p className="text-2xl font-bold text-sky-700">{blackboxOutcomeBreakdown.attack_discussion_only}</p>
              <p className="text-xs text-sky-800 mt-1">{t("report.discussionOnly")}</p>
            </div>
            <div className="rounded-xl border border-gray-200 bg-gray-100 p-4">
              <p className="text-2xl font-bold text-gray-700">{blackboxOutcomeBreakdown.no_injection_success}</p>
              <p className="text-xs text-gray-700 mt-1">{t("report.noSuccess")}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-2xl font-bold text-slate-700">{blackboxOutcomeBreakdown.unclassified}</p>
              <p className="text-xs text-slate-700 mt-1">{t("report.legacyUnclassified")}</p>
            </div>
          </div>
          {businessVerificationBreakdown && (
            <>
              <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("report.businessVerificationTitle")}</h2>
              <div className="grid grid-cols-4 gap-3 mb-6">
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <p className="text-2xl font-bold text-emerald-700">{businessVerificationBreakdown.probe_verified}</p>
              <p className="text-xs text-emerald-800 mt-1">{t("common.probeVerified")}</p>
                </div>
                <div className="rounded-xl border border-fuchsia-200 bg-fuchsia-50 p-4">
                  <p className="text-2xl font-bold text-fuchsia-700">{businessVerificationBreakdown.text_claim_only}</p>
              <p className="text-xs text-fuchsia-800 mt-1">{t("common.textClaimOnly")}</p>
                </div>
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
                  <p className="text-2xl font-bold text-rose-700">{businessVerificationBreakdown.probe_failed}</p>
              <p className="text-xs text-rose-800 mt-1">{t("common.probeFailed")}</p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-gray-100 p-4">
                  <p className="text-2xl font-bold text-gray-700">{businessVerificationBreakdown.not_applicable}</p>
              <p className="text-xs text-gray-700 mt-1">{t("common.notApplicable")}</p>
                </div>
              </div>
            </>
          )}
          <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("report.frameworkCoverage")}</h2>
          <CompliancePanel scanId={scanId} />
        </div>
      </div>

      {recommendations.length > 0 && (
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">{t("report.recommendations")}</h2>
          <ul className="space-y-2">
            {recommendations.map((rec, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-700">
                <Shield className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">{t("report.findings")} ({allFindings.length})</h2>
          <Link to={`/results/${scanId}`} className="text-xs text-indigo-600 hover:text-indigo-800 transition-colors">
            {t("report.viewAllResults")} →
          </Link>
        </div>
        <div className="divide-y divide-gray-100">
          {allFindings.map((f) => {
            const fColors = riskColors[f.level];
            const isExpanded = expanded.has(f.id);
            return (
              <div key={f.id}>
                <button
                  onClick={() => toggleExpand(f.id, f.case_id)}
                  className="w-full flex items-center gap-3 p-4 text-left hover:bg-gray-50 transition-colors"
                >
                  <AlertTriangle className={`w-4 h-4 ${fColors.text} shrink-0`} />
                  <span className="text-sm text-gray-900 flex-1">{f.attack_name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${fColors.bg} ${fColors.text}`}>
                    {f.level.toUpperCase()}
                  </span>
                  <span className={`text-[11px] px-2 py-0.5 rounded ${businessVerificationClasses(f.business_verification_status)}`}>
                    {businessVerificationLabel(f.business_verification_status, t)}
                  </span>
                  <span className={`text-[11px] px-2 py-0.5 rounded ${verdictClasses(f.verdict_status)}`}>
                    {verdictLabel(f.verdict_status, t)}
                  </span>
                  <span className="text-xs text-gray-500 font-mono">{f.owasp_id}</span>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  )}
                </button>
                {isExpanded && (
                  <div className="px-4 pb-4 space-y-3 text-sm">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">{t("report.cvssScore")}:</span>
                        <span
                          className={`text-xs font-mono font-bold ${
                            f.risk_score >= 9
                              ? "text-red-600"
                              : f.risk_score >= 7
                                ? "text-orange-600"
                                : f.risk_score >= 4
                                  ? "text-yellow-700"
                                  : "text-green-600"
                          }`}
                        >
                          {f.risk_score.toFixed(1)}/10
                        </span>
                      </div>
                      <span className="text-xs text-gray-300">|</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">{t("report.confidence")}:</span>
                        <span className="text-xs font-mono text-gray-700">
                          {((f.confidence ?? 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase mb-1">{t("report.attackPayload")}</p>
                      <pre className="bg-gray-50 border border-gray-100 p-3 rounded-lg text-gray-800 font-mono text-xs overflow-x-auto">
                        {f.payload_text}
                      </pre>
                    </div>
                    <ResponseEvaluationPanel evaluation={resolveResponseEvaluation(f)} t={t} />
                    {f.evidence && (
                      <div>
                      <p className="text-xs text-gray-500 uppercase mb-1">{t("report.evidence")}</p>
                        <p className="text-gray-700">{f.evidence}</p>
                      </div>
                    )}
                    {f.verdict_reason && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase mb-1">{t("report.verdictStatus")}</p>
                        <p className="text-gray-700">
                          <span className={`inline-flex mr-2 px-2 py-0.5 rounded text-[11px] ${verdictClasses(f.verdict_status)}`}>
                            {verdictLabel(f.verdict_status, t)}
                          </span>
                          {f.verdict_reason}
                        </p>
                      </div>
                    )}
                    <div>
                      <p className="text-xs text-gray-500 uppercase mb-1">{t("report.businessVerification")}</p>
                      <div className="rounded-lg border border-fuchsia-100 bg-fuchsia-50/70 p-3 space-y-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`inline-flex px-2 py-0.5 rounded text-[11px] ${businessVerificationClasses(f.business_verification_status)}`}>
                            {businessVerificationLabel(f.business_verification_status, t)}
                          </span>
                          {probeCountLabel(f.probe_summary) && (
                            <span className="text-[11px] text-slate-500">{probeCountLabel(f.probe_summary)}</span>
                          )}
                          {probeFailureType(f.probe_summary) && (
                            <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200 font-mono">
                              {probeFailureType(f.probe_summary)}
                            </span>
                          )}
                        </div>
                        {probeFailureReason(f.probe_summary) && (
                          <p className="text-sm text-slate-700">{probeFailureReason(f.probe_summary)}</p>
                        )}
                        {(f.probe_evidence_preview?.length ?? 0) > 0 && (
                          <div className="flex items-center gap-2 flex-wrap">
                            {f.probe_evidence_preview?.map((entry, index) => (
                              <span
                                key={`${f.id}-probe-preview-${index}`}
                                className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200"
                              >
                                {typeof entry["kind"] === "string" ? entry["kind"] : "evidence"}
                                {typeof entry["step"] === "string" ? ` @ ${entry["step"]}` : ""}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    {(f.blackbox_outcome || f.execution_mode || behaviorPills(f.behavior_flags).length > 0) && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase mb-1">{t("report.blackboxOutcome")}</p>
                        <div className="flex items-center gap-2 flex-wrap">
                          {f.blackbox_outcome && (
                            <span className={`inline-flex px-2 py-0.5 rounded text-[11px] ${outcomeClasses(f.blackbox_outcome)}`}>
                            {outcomeLabel(f.blackbox_outcome, t)}
                            </span>
                          )}
                          {f.execution_mode && (
                            <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-slate-50 text-slate-700 border border-slate-200">
                              {executionModeLabel(f.execution_mode, t)}
                            </span>
                          )}
                          {behaviorPills(f.behavior_flags, t).map((pill) => (
                            <span key={`${f.id}-${pill.label}`} className={`inline-flex px-2 py-0.5 rounded text-[11px] ${pill.tone}`}>
                              {pill.label}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {(f.attack_goal_score != null || f.utility_score != null || f.utility_explanation) && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase mb-1">{t("report.attackGoalScore")} & {t("report.utilityScore")}</p>
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
                          <div className="flex items-center gap-4 flex-wrap text-sm">
                            <span>
                              {t("report.attackGoalScore")}:{" "}
                              <span className={`font-mono font-semibold ${scoreTone(f.attack_goal_score)}`}>
                                {f.attack_goal_score != null ? f.attack_goal_score.toFixed(2) : "-"}
                              </span>
                            </span>
                            <span>
                              {t("report.utilityScore")}:{" "}
                              <span className={`font-mono font-semibold ${f.utility_score == null ? "text-gray-500" : f.utility_score >= 0.8 ? "text-emerald-700" : f.utility_score >= 0.5 ? "text-amber-700" : "text-rose-700"}`}>
                                {f.utility_score != null ? f.utility_score.toFixed(2) : "N/A"}
                              </span>
                            </span>
                          </div>
                          {f.utility_explanation && <p className="text-sm text-slate-700">{f.utility_explanation}</p>}
                        </div>
                      </div>
                    )}
                    {(f.control_assessment || f.control_summary) && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase mb-1">{t("results.controlSummary")}</p>
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                          <p className="text-sm text-slate-800">
                            {f.control_assessment && (
                              <span className={`inline-flex mr-2 px-2 py-0.5 rounded text-[11px] ${controlAssessmentClasses(f.control_assessment)}`}>
                              {controlAssessmentLabel(f.control_assessment, t)}
                              </span>
                            )}
                            {f.control_summary || t("report.noControlSummary")}
                          </p>
                        </div>
                      </div>
                    )}
                    <div>
                      <p className="text-xs text-gray-500 uppercase mb-1">{t("results.viewQuartetDetails")}</p>
                      {!f.case_id ? (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-slate-700">
                          {t("results.noCase")}
                        </div>
                      ) : caseDetailLoading.has(f.case_id) ? (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-slate-700 flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          {t("results.loadingDetails")}
                        </div>
                      ) : caseDetailErrors[f.case_id] ? (
                        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-rose-800">
                          {t("report.failedQuartetDetails")}: {caseDetailErrors[f.case_id]}
                        </div>
                      ) : caseDetails[f.case_id] ? (
                        <div className="space-y-3">
                          <ResponseEvaluationPanel evaluation={resolveResponseEvaluation(caseDetails[f.case_id])} t={t} />
                          <div className="flex items-center gap-2 flex-wrap">
                            {f.case_final_outcome && (
                              <span className={`inline-flex px-2 py-0.5 rounded text-[11px] ${controlAssessmentClasses(f.case_final_outcome)}`}>
                              {controlAssessmentLabel(f.case_final_outcome, t)}
                              </span>
                            )}
                            {f.quartet_present != null && (
                              <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200">
                              {f.quartet_present ? t("results.quartetPresent") : t("results.quartetMissing")}
                              </span>
                            )}
                            <span className={`inline-flex px-2 py-0.5 rounded text-[11px] ${businessVerificationClasses(caseDetails[f.case_id].business_verification_status)}`}>
                              {businessVerificationLabel(caseDetails[f.case_id].business_verification_status)}
                            </span>
                          </div>
                          {(probeFailureReason(caseDetails[f.case_id].probe_summary) ||
                            (Array.isArray(caseDetails[f.case_id].probe_evidence_json?.["evidence"]) &&
                              (caseDetails[f.case_id].probe_evidence_json!["evidence"] as unknown[]).length > 0)) && (
                            <div className="rounded-lg border border-fuchsia-100 bg-fuchsia-50/70 p-3 space-y-2">
                              {probeFailureReason(caseDetails[f.case_id].probe_summary) && (
                                <p className="text-sm text-slate-700">{probeFailureReason(caseDetails[f.case_id].probe_summary)}</p>
                              )}
                              {Array.isArray(caseDetails[f.case_id].probe_evidence_json?.["evidence"]) &&
                                (caseDetails[f.case_id].probe_evidence_json!["evidence"] as unknown[]).length > 0 && (
                                <pre className="bg-white border border-slate-200 p-3 rounded-lg text-slate-800 font-mono text-xs overflow-x-auto whitespace-pre-wrap max-h-48 overflow-y-auto">
                                  {JSON.stringify(caseDetails[f.case_id].probe_evidence_json, null, 2)}
                                </pre>
                              )}
                            </div>
                          )}
                          {caseDetails[f.case_id].variants.map((variant) => (
                            <div key={variant.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className={`inline-flex px-2 py-0.5 rounded text-[11px] ${variantClasses(variant.variant_type)}`}>
                                {variantLabel(variant.variant_type, t)}
                                </span>
                                {variant.is_primary && (
                                  <span className="inline-flex px-2 py-0.5 rounded text-[11px] bg-white text-slate-700 border border-slate-200">
                                    {t("common.primary")}
                                  </span>
                                )}
                              </div>
                              <ResponseEvaluationPanel evaluation={resolveResponseEvaluation(variant)} t={t} />
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
                        </div>
                      ) : (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-slate-700">
                          {t("report.quartetNotLoaded")}
                        </div>
                      )}
                    </div>
                    {!!f.rule_hits?.length && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase mb-1">{t("report.ruleEvidence")}</p>
                        <div className="space-y-2">
                          {f.rule_hits.map((hit: { rule: string; evidence: string }, index: number) => (
                            <div key={`${f.id}-hit-${index}`} className="rounded-lg border border-emerald-100 bg-emerald-50 p-3">
                              <p className="text-[11px] font-mono text-emerald-700">{hit.rule}</p>
                              <p className="text-xs text-emerald-900 mt-1">{hit.evidence}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {!!f.canary_provenance?.observations?.length && (
                      <CanaryJourney provenance={f.canary_provenance} t={t} />
                    )}
                    {f.explanation && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase mb-1">{t("report.analysis")}</p>
                        <p className="text-gray-700">{f.explanation}</p>
                      </div>
                    )}
                    {f.remediation && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase mb-1">{t("report.remediation")}</p>
                        <p className="text-indigo-700">{f.remediation}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
          {allFindings.length === 0 && (
            <div className="p-8 text-center text-gray-500">{t("report.noVulnerabilities")}</div>
          )}
        </div>
      </div>
    </div>
  );
}
