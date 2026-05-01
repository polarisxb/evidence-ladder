import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  FlaskConical,
  Loader2,
  Pencil,
  Save,
  Search,
  Tag,
  Trash2,
  XCircle,
} from "lucide-react";
import {
  batchDeleteCalibrationSamples,
  batchSampleProduction,
  createCalibrationRun,
  deleteAllCalibrationSamples,
  deleteCalibrationSample,
  getCalibrationSummary,
  listCalibrationRuns,
  listCalibrationSamples,
  updateCalibrationSample,
} from "../api/judgeCalibration";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";
import { getCaseDetail } from "../api/cases";
import type {
  AttackCaseDetail,
  AttackCaseVariant,
  JudgeCalibrationBreakdownItem,
  JudgeCalibrationRun,
  JudgeCalibrationSample,
  JudgeCalibrationSummary,
  JudgeGoldLabel,
  JudgeMisclassificationPreview,
} from "../types";

const VERDICT_STATUS_OPTIONS = [
  "rule_verified",
  "manual_verified",
  "ai_suspected",
  "manual_review_needed",
  "false_positive",
  "passed",
  "not_evaluable",
] as const;

type SampleFilter = "all" | "unlabeled" | "labeled" | "mismatch";

// UI view state we persist across navigation. When the user deep-links
// into ScanResults to look at a case and then comes back, we want the
// sample list still open, the same filter / search applied, and the
// runs history in the same collapsed state — this is “returning
// completely”. sessionStorage (not localStorage) so closing the tab
// still wipes the state.
const VIEW_STATE_KEY = "judgeCalibration.viewState.v1";

type PersistedViewState = {
  showSamples: boolean;
  sampleFilter: SampleFilter;
  sampleSearch: string;
  runsCollapsed: boolean;
};

function loadViewState(): Partial<PersistedViewState> {
  try {
    const raw = sessionStorage.getItem(VIEW_STATE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Partial<PersistedViewState>;
  } catch {
    return {};
  }
}

function saveViewState(state: PersistedViewState) {
  try {
    sessionStorage.setItem(VIEW_STATE_KEY, JSON.stringify(state));
  } catch {
    /* private mode / quota — non-critical, just lose persistence */
  }
}

function pctLabel(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function misclassTypeTone(t: string) {
  switch (t) {
    case "false_positive": return "bg-rose-50 text-rose-700 border border-rose-200";
    case "false_negative": return "bg-amber-50 text-amber-800 border border-amber-200";
    case "verdict_drift": return "bg-sky-50 text-sky-700 border border-sky-200";
    default: return "bg-gray-100 text-gray-600 border border-gray-200";
  }
}

// Rule-of-thumb threshold below which rates computed from N samples are
// statistically unreliable. Chosen at 30 because that's the classical
// "small-sample" boundary; the UI just warns, it does not suppress numbers.
const LOW_SAMPLE_THRESHOLD = 30;

function MetricCard({
  label,
  value,
  tone,
  help,
  lowSample,
  lowSampleLabel,
}: {
  label: string;
  value: string;
  tone: string;
  help?: string;
  lowSample?: boolean;
  lowSampleLabel?: string;
}) {
  return (
    <div className="card p-5 flex flex-col gap-2">
      <p className={`text-2xl font-bold font-mono ${tone}`}>{value}</p>
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</p>
        {lowSample && (
          <span
            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200"
            title={lowSampleLabel}
          >
            <AlertTriangle className="w-2.5 h-2.5" />
            {lowSampleLabel}
          </span>
        )}
      </div>
      {help && <p className="text-xs text-gray-400 leading-snug">{help}</p>}
    </div>
  );
}

/**
 * 2×2 confusion matrix card.
 *
 * Reads TP/FP/TN/FN straight from the backend (see
 * ``JudgeConfusionMatrix``). The 2×2 is meaningfully more informative than
 * the precision/recall/FPR numbers next to it because small datasets can
 * make e.g. "100% precision" look impressive when it's really "1 / 1".
 */
function ConfusionMatrixCard({
  cm,
  t,
}: {
  cm: { true_positive: number; false_positive: number; true_negative: number; false_negative: number; evaluated: number };
  t: (key: string) => string;
}) {
  const Cell = ({
    n,
    label,
    tone,
    help,
  }: {
    n: number;
    label: string;
    tone: string;
    help: string;
  }) => (
    <div className={`rounded-lg border p-3 flex flex-col gap-1 ${tone}`}>
      <p className="font-mono text-2xl font-bold">{n}</p>
      <p className="text-[11px] font-semibold uppercase tracking-wide">{label}</p>
      <p className="text-[11px] opacity-75">{help}</p>
    </div>
  );

  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-3">
        <p className="text-sm font-semibold text-gray-800">{t("calibration.confusionMatrix")}</p>
        <span className="text-xs text-gray-400">
          N = {cm.evaluated}
        </span>
      </div>
      {/* 2x2 grid. Rows = judge's decision; columns = gold truth. */}
      <div className="grid grid-cols-[auto_1fr_1fr] gap-2 items-stretch text-xs">
        <div />
        <div className="text-center text-[11px] font-semibold uppercase tracking-wide text-gray-500 py-1">
          {t("calibration.goldPositive")}
        </div>
        <div className="text-center text-[11px] font-semibold uppercase tracking-wide text-gray-500 py-1">
          {t("calibration.goldNegative")}
        </div>

        <div className="flex items-center text-[11px] font-semibold uppercase tracking-wide text-gray-500 pr-2 justify-end">
          {t("calibration.judgePositive")}
        </div>
        <Cell
          n={cm.true_positive}
          label="TP"
          tone="border-emerald-200 bg-emerald-50 text-emerald-800"
          help={t("calibration.tpHelp")}
        />
        <Cell
          n={cm.false_positive}
          label="FP"
          tone="border-rose-200 bg-rose-50 text-rose-800"
          help={t("calibration.fpHelp")}
        />

        <div className="flex items-center text-[11px] font-semibold uppercase tracking-wide text-gray-500 pr-2 justify-end">
          {t("calibration.judgeNegative")}
        </div>
        <Cell
          n={cm.false_negative}
          label="FN"
          tone="border-amber-200 bg-amber-50 text-amber-800"
          help={t("calibration.fnHelp")}
        />
        <Cell
          n={cm.true_negative}
          label="TN"
          tone="border-gray-200 bg-gray-50 text-gray-700"
          help={t("calibration.tnHelp")}
        />
      </div>
    </div>
  );
}

function BreakdownTable({ rows }: { rows: JudgeCalibrationBreakdownItem[] }) {
  const { t: _bt } = useLocale();
  if (!rows.length) return <p className="text-xs text-gray-400">{_bt("common.noData")}</p>;
  return (
    <div className="divide-y divide-gray-100 rounded-lg border border-gray-200 overflow-hidden">
      {rows.map((r) => (
        <div key={r.key} className="grid grid-cols-5 gap-2 px-3 py-2 text-xs items-center hover:bg-gray-50">
          <span className="col-span-2 font-medium text-gray-800 truncate">{r.key}</span>
          <span className="text-center text-gray-500">{r.sample_count}</span>
          <span className={`text-center font-mono ${r.precision == null ? "text-gray-400" : r.precision >= 0.8 ? "text-emerald-700" : r.precision >= 0.6 ? "text-amber-700" : "text-rose-700"}`}>
            {pctLabel(r.precision)}
          </span>
          <span className={`text-center font-mono ${r.false_positive_rate == null ? "text-gray-400" : r.false_positive_rate <= 0.1 ? "text-emerald-700" : r.false_positive_rate <= 0.25 ? "text-amber-700" : "text-rose-700"}`}>
            {pctLabel(r.false_positive_rate)}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * Historical calibration runs panel.
 *
 * Renders the most recent calibration runs as a compact list, reading
 * headline metrics from each run's frozen ``summary_json``. This lets
 * users compare "before / after" a judge prompt change without leaving
 * the page — the top of the page shows the current live summary, and
 * this panel shows what past runs measured.
 *
 * Why read ``summary_json`` rather than re-computing: the calibration
 * runner explicitly freezes the metrics at run time so a later change to
 * the sample set doesn't retroactively rewrite historical measurements.
 */
function RunsHistoryPanel({
  runs,
  loading,
  collapsed,
  onToggle,
  t,
}: {
  runs: JudgeCalibrationRun[];
  loading: boolean;
  collapsed: boolean;
  onToggle: () => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  if (runs.length === 0 && !loading) return null;

  function fmtPct(v: unknown): string {
    if (typeof v !== "number" || Number.isNaN(v)) return "—";
    return `${(v * 100).toFixed(1)}%`;
  }

  function runStatusTone(status: string) {
    switch (status) {
      case "completed": return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "running": return "bg-sky-50 text-sky-700 border-sky-200";
      case "failed": return "bg-rose-50 text-rose-700 border-rose-200";
      default: return "bg-gray-100 text-gray-600 border-gray-200";
    }
  }

  return (
    <div className="card overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50"
      >
        <div className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 text-indigo-500" />
          <span className="text-sm font-semibold text-gray-800">
            {t("calibration.runsHistoryTitle")} ({runs.length})
          </span>
        </div>
        {collapsed ? (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        )}
      </button>
      {!collapsed && (
        <div className="divide-y divide-gray-100">
          {runs.map((run) => {
            const s = (run.summary_json ?? {}) as Record<string, unknown>;
            const precision = s.judge_precision_at_gold;
            const recall = s.judge_recall_at_gold;
            const fpr = s.judge_false_positive_rate;
            const when = run.completed_at || run.started_at || run.created_at;
            const whenStr = new Date(when).toLocaleString();
            return (
              <div key={run.id} className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium text-gray-800 truncate">
                      {run.name || `Run ${run.id.slice(0, 8)}`}
                    </p>
                    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] border ${runStatusTone(run.status)}`}>
                      {run.status}
                    </span>
                    <span className="text-[11px] text-gray-400 tabular-nums">{whenStr}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 flex-wrap text-[11px] text-gray-500 font-mono">
                    <span>N = <span className="text-gray-800">{run.sample_count}</span></span>
                    <span>P = <span className="text-gray-800">{fmtPct(precision)}</span></span>
                    <span>R = <span className="text-gray-800">{fmtPct(recall)}</span></span>
                    <span>FPR = <span className="text-gray-800">{fmtPct(fpr)}</span></span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Variant badge colour tone based on variant_type. */
function variantTone(vt: string): string {
  switch (vt) {
    case "attack":
    case "primary_attack":
      return "bg-rose-50 text-rose-700 border-rose-200";
    case "clean":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "quoted_attack":
      return "bg-amber-50 text-amber-800 border-amber-200";
    case "benign_distractor":
      return "bg-sky-50 text-sky-700 border-sky-200";
    default:
      return "bg-gray-100 text-gray-700 border-gray-200";
  }
}

/** Render one attack variant row (request + response) as a collapsible block. */
function VariantCard({
  variant,
  defaultOpen,
  t,
}: {
  variant: AttackCaseVariant;
  defaultOpen: boolean;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const request = variant.request_text ?? "";
  const response = variant.response_text ?? "";
  const error = variant.response_error;

  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-50/60 hover:bg-gray-100 text-left"
      >
        <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] border font-mono ${variantTone(variant.variant_type)}`}>
          {variant.variant_type}
        </span>
        {variant.is_primary && (
          <span className="inline-flex px-1.5 py-0.5 rounded text-[10px] border border-rose-300 bg-rose-100 text-rose-800 font-semibold">
            {t("calibration.detailPrimary")}
          </span>
        )}
        <span className="text-[11px] text-gray-500 ml-auto">
          {variant.response_status ? `HTTP ${variant.response_status}` : null}
          {variant.latency_ms != null ? ` · ${variant.latency_ms}ms` : null}
        </span>
        {open ? <ChevronUp className="w-3.5 h-3.5 text-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400" />}
      </button>
      {open && (
        <div className="px-3 py-3 space-y-2 text-xs">
          <div>
            <p className="font-semibold uppercase tracking-wide text-gray-500 mb-1 text-[10px]">
              {t("calibration.detailRequest")}
            </p>
            <pre className="whitespace-pre-wrap break-words font-mono text-[12px] text-gray-800 bg-gray-50 rounded p-2 max-h-80 overflow-auto">
              {request || "—"}
            </pre>
          </div>
          <div>
            <p className="font-semibold uppercase tracking-wide text-gray-500 mb-1 text-[10px]">
              {t("calibration.detailResponse")}
            </p>
            {error ? (
              <pre className="whitespace-pre-wrap break-words font-mono text-[12px] text-rose-700 bg-rose-50 border border-rose-200 rounded p-2 max-h-80 overflow-auto">
                {error}
              </pre>
            ) : (
              <pre className="whitespace-pre-wrap break-words font-mono text-[12px] text-gray-800 bg-gray-50 rounded p-2 max-h-80 overflow-auto">
                {response || "—"}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Async-loaded case detail section rendered inside ``GoldLabelModal``.
 *
 * The Gold Label annotator needs to see *what actually happened* in the
 * case (attack prompt, target response, quartet comparison) before
 * deciding whether the judge's verdict was correct. Loading this inline
 * keeps the workflow on one screen — no navigation, no lost context.
 *
 * Fetches ``AttackCaseDetail`` once on mount; shows a skeleton while
 * loading, an error card on failure (the user can still annotate based
 * on the snapshot fields above if the detail fails to load).
 */
function CaseDetailSection({
  attackCaseId,
  t,
}: {
  attackCaseId: string;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  const [detail, setDetail] = useState<AttackCaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    getCaseDetail(attackCaseId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [attackCaseId]);

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50/40 p-4 flex items-center gap-2 text-sm text-gray-500">
        <Loader2 className="w-4 h-4 animate-spin" />
        {t("calibration.detailLoading")}
      </div>
    );
  }
  if (err || !detail) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
        {t("calibration.detailLoadFailed")}: {err ?? "not found"}
      </div>
    );
  }

  // Variants: primary first, then the three control variants, then anything
  // else. ``is_primary`` flag has final say; fallback on variant_type.
  const variants = [...(detail.variants ?? [])].sort((a, b) => {
    const score = (v: AttackCaseVariant) => {
      if (v.is_primary) return 0;
      switch (v.variant_type) {
        case "attack":
        case "primary_attack": return 0;
        case "clean": return 1;
        case "quoted_attack": return 2;
        case "benign_distractor": return 3;
        default: return 4;
      }
    };
    return score(a) - score(b);
  });

  return (
    <div className="space-y-3">
      {/* Attack summary strip */}
      <div className="rounded-lg border border-gray-200 bg-white p-3 space-y-1.5">
        <p className="text-sm font-semibold text-gray-900">{detail.attack_name}</p>
        <div className="flex items-center gap-2 flex-wrap text-[11px]">
          <span className="inline-flex px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono">
            {detail.category}
          </span>
          <span className="inline-flex px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono">
            {detail.technique}
          </span>
          {detail.case_final_outcome && (
            <span className="inline-flex px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
              {detail.case_final_outcome}
            </span>
          )}
          {detail.business_verification_status && (
            <span className="inline-flex px-1.5 py-0.5 rounded bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200">
              {detail.business_verification_status}
            </span>
          )}
          {detail.control_assessment && (
            <span className="inline-flex px-1.5 py-0.5 rounded bg-teal-50 text-teal-700 border border-teal-200">
              {detail.control_assessment}
            </span>
          )}
        </div>
        {detail.verdict_reason && (
          <div className="pt-2 border-t border-gray-100">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500 mb-1">
              {t("calibration.detailJudgeReason")}
            </p>
            <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">
              {detail.verdict_reason}
            </p>
          </div>
        )}
      </div>

      {/* Variant cards.

          All variants default to OPEN so the quartet (attack / clean /
          quoted_attack / benign_distractor) is visible at a glance when
          annotating — the annotator can always collapse individual
          cards if they get in the way. The header shows how the case
          was set up (full quartet vs legacy single-attack) so the user
          understands whether the absence of control variants is a data
          issue or just a case that pre-dates quartet_v1. */}
      {variants.length === 0 ? (
        <p className="text-xs text-gray-400 italic">{t("calibration.detailNoVariants")}</p>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap text-[11px] text-gray-500">
            <span>
              {t("calibration.detailVariantsLabel", { n: variants.length })}
            </span>
            {variants.length >= 4 ? (
              <span className="inline-flex px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                {t("calibration.detailQuartetFull")}
              </span>
            ) : variants.length > 1 ? (
              <span className="inline-flex px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
                {t("calibration.detailQuartetPartial", { n: variants.length })}
              </span>
            ) : (
              <span className="inline-flex px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 border border-gray-200">
                {t("calibration.detailQuartetNone")}
              </span>
            )}
            {detail.protocol_version && (
              <span className="font-mono text-gray-400">{detail.protocol_version}</span>
            )}
          </div>
          {variants.map((v) => (
            <VariantCard key={v.id} variant={v} defaultOpen={true} t={t} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Read-only modal that shows just the case detail — no Gold Label form.
 *
 * Entry point for the "查看 Case" button on a sample row or a
 * misclassification preview: the user wants to inspect the case
 * (attack prompt, target response, quartet) without committing to
 * annotating it right now. Clicking "开始标注" hands off to the full
 * ``GoldLabelModal`` via the optional ``onStartAnnotate`` callback.
 */
function CaseDetailOnlyModal({
  attackCaseId,
  onClose,
  onStartAnnotate,
  t,
}: {
  attackCaseId: string;
  onClose: () => void;
  onStartAnnotate?: () => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3 shrink-0">
          <FlaskConical className="w-5 h-5 text-indigo-500" />
          <h3 className="text-base font-semibold text-gray-900">
            {t("calibration.viewCaseModalTitle")}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto text-gray-400 hover:text-gray-700"
          >
            <XCircle className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <CaseDetailSection attackCaseId={attackCaseId} t={t} />
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex items-center gap-2 justify-end shrink-0">
          {onStartAnnotate && (
            <button
              type="button"
              onClick={onStartAnnotate}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-700 text-sm hover:bg-indigo-100"
            >
              <Tag className="w-4 h-4" />
              {t("calibration.startAnnotate")}
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm hover:bg-gray-800"
          >
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Modal for annotating a calibration sample with a Gold Label.
 *
 * The Gold Label is the human expert's "ground truth" verdict for this
 * case. The calibration run later compares the frozen ``judge_output``
 * (what the AI judge decided at scan time) against this label to derive
 * precision / recall / FPR metrics.
 *
 * We pre-fill the form from the judge's own output so the common case
 * ("I agree with the judge") is a single click, and only disagreements
 * require editing.
 */
function GoldLabelModal({
  sample,
  onSave,
  onClose,
  t,
}: {
  sample: JudgeCalibrationSample;
  onSave: (sampleId: string, payload: {
    gold_label: JudgeGoldLabel;
    gold_rationale: string | undefined;
    labeler: string | undefined;
  }) => Promise<void>;
  onClose: () => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  const judgeOutput = (sample.judge_output ?? {}) as Record<string, unknown>;
  const existingGold = (sample.gold_label ?? {}) as Record<string, unknown>;

  const defaultReportable =
    typeof existingGold.reportable === "boolean"
      ? Boolean(existingGold.reportable)
      : Boolean(judgeOutput.reportable);
  const defaultVerdict =
    (typeof existingGold.verdict_status === "string" && existingGold.verdict_status) ||
    (typeof judgeOutput.verdict_status === "string" && (judgeOutput.verdict_status as string)) ||
    "rule_verified";

  const [reportable, setReportable] = useState<boolean>(defaultReportable);
  const [verdictStatus, setVerdictStatus] = useState<string>(defaultVerdict);
  const [rationale, setRationale] = useState<string>(sample.gold_rationale ?? "");
  const [labeler, setLabeler] = useState<string>(sample.labeler ?? "");
  const [saving, setSaving] = useState(false);

  async function handleSubmit() {
    setSaving(true);
    try {
      await onSave(sample.id, {
        gold_label: { reportable, verdict_status: verdictStatus },
        gold_rationale: rationale.trim() || undefined,
        labeler: labeler.trim() || undefined,
      });
    } finally {
      setSaving(false);
    }
  }

  // Summarize what the judge said so the human can compare.
  const judgeVerdict = typeof judgeOutput.verdict_status === "string" ? judgeOutput.verdict_status : "—";
  const judgeReportable =
    typeof judgeOutput.reportable === "boolean" ? Boolean(judgeOutput.reportable) : null;
  // The case is rendered inline via CaseDetailSection, so we only need
  // the attack_case_id to drive that component (no more scan_id route).
  const attackCaseId = sample.attack_case_id;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      {/* Modal is now max-w-3xl + max-h-[90vh] + flex-col so the embedded
          case detail (variants, long response text) has room to breathe
          and the middle scrolls independently of header/footer. */}
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3 shrink-0">
          <Tag className="w-5 h-5 text-indigo-500" />
          <h3 className="text-base font-semibold text-gray-900">
            {t("calibration.labelModalTitle")}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto text-gray-400 hover:text-gray-700"
          >
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Full case detail (request / response / quartet variants).
              Loaded inline so the annotator never leaves this modal. */}
          {attackCaseId ? (
            <CaseDetailSection attackCaseId={attackCaseId} t={t} />
          ) : (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              {t("calibration.detailNoCaseId")}
            </div>
          )}

          {/* Judge's own verdict — read-only, for reference */}
          <div className="rounded-lg border border-gray-200 bg-gray-50/60 p-3 space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t("calibration.judgeSaidLabel")}
            </p>
            <div className="flex items-center gap-2 flex-wrap text-xs">
              <span className="inline-flex px-2 py-0.5 rounded bg-white text-gray-700 border border-gray-200 font-mono">
                {judgeVerdict}
              </span>
              {judgeReportable !== null && (
                <span className={`inline-flex px-2 py-0.5 rounded text-[11px] ${judgeReportable ? "bg-rose-50 text-rose-700 border border-rose-200" : "bg-emerald-50 text-emerald-700 border border-emerald-200"}`}>
                  {judgeReportable ? t("calibration.reportableYes") : t("calibration.reportableNo")}
                </span>
              )}
              {/* No "View Case" link here — the full case detail is already
                  rendered above in CaseDetailSection, so an extra jump
                  would be redundant. */}
            </div>
          </div>

          {/* Gold label editor */}
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                {t("calibration.labelReportable")}
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setReportable(true)}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors ${reportable ? "bg-rose-50 border-rose-300 text-rose-800" : "bg-white border-gray-200 text-gray-600 hover:border-gray-400"}`}
                >
                  {t("calibration.reportableYes")}
                </button>
                <button
                  type="button"
                  onClick={() => setReportable(false)}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors ${!reportable ? "bg-emerald-50 border-emerald-300 text-emerald-800" : "bg-white border-gray-200 text-gray-600 hover:border-gray-400"}`}
                >
                  {t("calibration.reportableNo")}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                {t("calibration.labelVerdictStatus")}
              </label>
              <select
                value={verdictStatus}
                onChange={(e) => setVerdictStatus(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg text-gray-900 focus:border-indigo-400 focus:outline-none font-mono"
              >
                {VERDICT_STATUS_OPTIONS.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                {t("calibration.labelRationale")}
              </label>
              <textarea
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder={t("calibration.labelRationalePlaceholder")}
                rows={3}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg text-gray-900 placeholder:text-gray-400 focus:border-indigo-400 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                {t("calibration.labelLabeler")}
              </label>
              <input
                type="text"
                value={labeler}
                onChange={(e) => setLabeler(e.target.value)}
                placeholder={t("calibration.labelLabelerPlaceholder")}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg text-gray-900 placeholder:text-gray-400 focus:border-indigo-400 focus:outline-none"
              />
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex items-center gap-2 justify-end shrink-0">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {t("common.cancel")}
          </button>
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gray-900 text-white text-sm hover:bg-gray-800 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? t("common.saving") : t("calibration.labelSave")}
          </button>
        </div>
      </div>
    </div>
  );
}

export function JudgeCalibration() {
  const [summary, setSummary] = useState<JudgeCalibrationSummary | null>(null);
  const [sampleCount, setSampleCount] = useState<number | null>(null);
  const [samples, setSamples] = useState<JudgeCalibrationSample[]>([]);
  // ``showSamples`` is initialised from sessionStorage so returning from
  // a deep-link to ScanResults finds the list exactly as the user left it.
  const [showSamples, setShowSamples] = useState(() => loadViewState().showSamples ?? false);
  const [labelingSample, setLabelingSample] = useState<JudgeCalibrationSample | null>(null);
  // Read-only "view case" modal driven by this state. Holds attack_case_id
  // plus optionally the source sample so we can offer "开始标注” as a
  // shortcut into GoldLabelModal without re-clicking.
  const [viewing, setViewing] = useState<{ caseId: string; sample?: JudgeCalibrationSample } | null>(null);
  // Batch-selection state for the sample list. Stored as a Set so add /
  // remove are O(1). Cleared whenever samples are refreshed (after a
  // delete, label, or re-sample) to avoid stale ids lingering.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  // Sample list filter / search. Narrows the rendered list purely on the
  // client — we already loaded up to 100 samples, so re-filtering in
  // memory is cheap and avoids re-requesting for every pill click.
  const [sampleFilter, setSampleFilter] = useState<SampleFilter>(() => loadViewState().sampleFilter ?? "all");
  const [sampleSearch, setSampleSearch] = useState(() => loadViewState().sampleSearch ?? "");
  // History of past calibration runs. Loaded alongside samples + summary
  // so the history panel is populated on first paint.
  const [runs, setRuns] = useState<JudgeCalibrationRun[]>([]);
  const [runsCollapsed, setRunsCollapsed] = useState(() => loadViewState().runsCollapsed ?? true);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [expandedBreakdown, setExpandedBreakdown] = useState<string | null>(null);
  const [expandedMisclass, setExpandedMisclass] = useState(false);
  // Batch sampling panel state
  const [showBatchPanel, setShowBatchPanel] = useState(false);
  const [batchLimit, setBatchLimit] = useState(50);
  const [batchCategory, setBatchCategory] = useState("");
  const [batching, setBatching] = useState(false);
  const { toast } = useToast();
  const { t } = useLocale();

  async function refreshSamples() {
    try {
      const res = await listCalibrationSamples({ limit: 100 });
      setSamples(res.data);
      setSampleCount(res.count);
      // Drop any selected ids that no longer exist in the refreshed list
      // (e.g. after a batch delete). Intersecting avoids stale selection.
      setSelectedIds((prev) => {
        const alive = new Set(res.data.map((s) => s.id));
        const next = new Set<string>();
        prev.forEach((id) => alive.has(id) && next.add(id));
        return next;
      });
    } catch (err) {
      toast("error", `${t("calibration.loadSamplesFailed")}: ${err instanceof Error ? err.message : err}`);
    }
  }

  function toggleSelectOne(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // Filter the sample list by the active pill + free-text search. Memoized
  // so we don't recompute on unrelated renders (Modal open/close etc.).
  const filteredSamples = useMemo(() => {
    const q = sampleSearch.trim().toLowerCase();
    return samples.filter((s) => {
      const jo = (s.judge_output ?? {}) as Record<string, unknown>;
      const gold = (s.gold_label ?? null) as Record<string, unknown> | null;
      const isLabeled = gold !== null;
      const jr = typeof jo.reportable === "boolean" ? Boolean(jo.reportable) : null;
      const gr = gold && typeof gold.reportable === "boolean" ? Boolean(gold.reportable) : null;
      const isMismatch = isLabeled && jr !== null && gr !== null && jr !== gr;

      if (sampleFilter === "unlabeled" && isLabeled) return false;
      if (sampleFilter === "labeled" && !isLabeled) return false;
      if (sampleFilter === "mismatch" && !isMismatch) return false;

      if (q) {
        const haystack = [
          s.id,
          s.attack_case_id ?? "",
          typeof jo.verdict_status === "string" ? jo.verdict_status : "",
          gold && typeof gold.verdict_status === "string" ? (gold.verdict_status as string) : "",
          s.source_type,
        ].join(" ").toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [samples, sampleFilter, sampleSearch]);

  function toggleSelectAll() {
    // Select-all operates on the *currently visible* (filtered) list, not
    // the full dataset — avoids the footgun where a user filters to
    // "已标注", clicks all, then deletes hidden un-labeled samples too.
    setSelectedIds((prev) => {
      const visibleIds = filteredSamples.map((s) => s.id);
      const allVisibleSelected =
        visibleIds.length > 0 && visibleIds.every((id) => prev.has(id));
      if (allVisibleSelected) {
        const next = new Set(prev);
        visibleIds.forEach((id) => next.delete(id));
        return next;
      }
      const next = new Set(prev);
      visibleIds.forEach((id) => next.add(id));
      return next;
    });
  }

  async function refreshRuns() {
    try {
      const res = await listCalibrationRuns({ limit: 20 });
      setRuns(res.data);
    } catch {
      /* non-critical — history panel is optional, fail silently */
    }
  }

  // Persist view-state whenever any of the tracked fields change. Cheap
  // (synchronous write to sessionStorage).
  useEffect(() => {
    saveViewState({ showSamples, sampleFilter, sampleSearch, runsCollapsed });
  }, [showSamples, sampleFilter, sampleSearch, runsCollapsed]);

  useEffect(() => {
    void (async () => {
      try {
        const [s, samplesRes, runsRes] = await Promise.all([
          getCalibrationSummary().catch(() => null),
          listCalibrationSamples({ limit: 100 }).catch(() => ({ data: [] as JudgeCalibrationSample[], count: 0 })),
          listCalibrationRuns({ limit: 20 }).catch(() => ({ data: [] as JudgeCalibrationRun[], count: 0 })),
        ]);
        setSummary(s);
        setSamples(samplesRes.data);
        setSampleCount(samplesRes.count);
        setRuns(runsRes.data);
      } catch {
        /* best-effort */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleBatchSample() {
    setBatching(true);
    try {
      const res = await batchSampleProduction({
        limit: batchLimit,
        category: batchCategory || undefined,
      });
      toast("success", t("calibration.batchSampleSuccess", { count: res.count }));
      setShowBatchPanel(false);
      await refreshSamples();
    } catch (err) {
      toast("error", `${t("calibration.batchSampleFailed")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setBatching(false);
    }
  }

  async function handleSaveLabel(
    sampleId: string,
    payload: {
      gold_label: JudgeGoldLabel;
      gold_rationale: string | undefined;
      labeler: string | undefined;
    },
  ) {
    try {
      await updateCalibrationSample(sampleId, payload);
      toast("success", t("calibration.labelSaveSuccess"));
      setLabelingSample(null);
      await refreshSamples();
      // Re-compute summary: labeled_count and noData banner update immediately.
      const updatedSummary = await getCalibrationSummary().catch(() => null);
      setSummary(updatedSummary);
    } catch (err) {
      toast("error", `${t("calibration.labelSaveFailed")}: ${err instanceof Error ? err.message : err}`);
    }
  }

  async function handleDeleteSample(sampleId: string) {
    // Native confirm() is sufficient here: deletion is destructive but
    // reversible by re-sampling from the same scan, so a full modal would
    // be overkill.
    if (!window.confirm(t("calibration.deleteConfirm"))) return;
    try {
      await deleteCalibrationSample(sampleId);
      toast("success", t("calibration.deleteSuccess"));
      await refreshSamples();
      // Summary counts (sample_count / labeled_count / precision-recall) are
      // all derived from the live sample set — refresh it so the header
      // banner and metric cards reflect the deletion immediately.
      const updatedSummary = await getCalibrationSummary().catch(() => null);
      setSummary(updatedSummary);
    } catch (err) {
      toast("error", `${t("calibration.deleteFailed")}: ${err instanceof Error ? err.message : err}`);
    }
  }

  async function handleBatchDelete() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (!window.confirm(t("calibration.batchDeleteConfirm", { n: ids.length }))) return;
    setBulkDeleting(true);
    try {
      const deleted = await batchDeleteCalibrationSamples(ids);
      toast("success", t("calibration.batchDeleteSuccess", { n: deleted }));
      await refreshSamples();
      const updatedSummary = await getCalibrationSummary().catch(() => null);
      setSummary(updatedSummary);
    } catch (err) {
      toast("error", `${t("calibration.batchDeleteFailed")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setBulkDeleting(false);
    }
  }

  async function handleDeleteAll() {
    if (!window.confirm(t("calibration.deleteAllConfirm"))) return;
    setBulkDeleting(true);
    try {
      const deleted = await deleteAllCalibrationSamples();
      toast("success", t("calibration.batchDeleteSuccess", { n: deleted }));
      await refreshSamples();
      const updatedSummary = await getCalibrationSummary().catch(() => null);
      setSummary(updatedSummary);
    } catch (err) {
      toast("error", `${t("calibration.batchDeleteFailed")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setBulkDeleting(false);
    }
  }

  async function handleRunCalibration() {
    setRunning(true);
    try {
      await createCalibrationRun({ name: `Run ${new Date().toISOString().slice(0, 16)}` });
      const updated = await getCalibrationSummary();
      setSummary(updated);
      toast("success", t("calibration.runSuccess"));
      // Auto-expand the history panel the first time a run completes so
      // the user sees their new run land — a subtle success confirmation
      // beyond the toast.
      setRunsCollapsed(false);
      await refreshRuns();
    } catch (err) {
      toast("error", `${t("calibration.runFailed")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-400 gap-2">
        <Loader2 className="w-5 h-5 animate-spin" />
        {t("calibration.loading")}
      </div>
    );
  }

  const noData = !summary || summary.labeled_count === 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t("calibration.title")}</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {t("calibration.subtitle")}
          </p>
        </div>
        <button
          type="button"
          disabled={running || sampleCount === 0}
          onClick={() => void handleRunCalibration()}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-900 text-white text-sm hover:bg-gray-800 disabled:opacity-50 transition-colors"
        >
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <FlaskConical className="w-4 h-4" />}
          {running ? t("calibration.running") : t("calibration.runCalibration")}
        </button>
      </div>

      {/* Sample inventory banner */}
      <div className="space-y-3">
        <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
          <Activity className="w-4 h-4 text-gray-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-700">
              <span className="font-semibold">{sampleCount ?? "—"}</span> {t("calibration.samples")}
              {summary && summary.labeled_count > 0 && (
                <> · <span className="font-semibold text-indigo-700">{summary.labeled_count}</span> {t("calibration.goldLabels")}</>
              )}
              {sampleCount === 0 && (
                <span className="ml-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                  {t("calibration.noSamples")}
                </span>
              )}
            </p>
            {/* Labeling progress. Ratio labeled/total (from the server's
                sampleCount), not labeled/evaluated. The bar color also
                signals completeness: < 30% amber, 30-80% indigo, > 80%
                emerald — matches the classical "coverage" intuition. */}
            {(() => {
              const total = sampleCount ?? 0;
              if (total === 0) return null;
              const labeled = summary?.labeled_count ?? 0;
              const pct = Math.round((labeled / total) * 100);
              const barTone =
                pct >= 80 ? "bg-emerald-500"
                : pct >= 30 ? "bg-indigo-500"
                : "bg-amber-400";
              return (
                <div className="mt-1.5 flex items-center gap-2">
                  <div className="flex-1 h-1.5 rounded-full bg-gray-200 overflow-hidden">
                    <div className={`h-full ${barTone} transition-[width] duration-300`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-[11px] text-gray-500 tabular-nums font-mono shrink-0">
                    {labeled}/{total} · {pct}%
                  </span>
                </div>
              );
            })()}
          </div>
          <button
            type="button"
            onClick={() => setShowSamples((v) => !v)}
            disabled={(sampleCount ?? 0) === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border border-gray-200 bg-white text-gray-700 hover:border-gray-400 disabled:opacity-50 transition-colors"
          >
            {showSamples ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            {showSamples ? t("calibration.hideSamples") : t("calibration.showSamples")}
          </button>
          <button
            type="button"
            onClick={() => setShowBatchPanel((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border border-gray-200 bg-white text-gray-700 hover:border-gray-400 transition-colors"
          >
            {t("calibration.batchSample")}
          </button>
        </div>

        {showSamples && samples.length > 0 && (
          <div className="card overflow-hidden">
            {/* Filter + search toolbar */}
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-100 bg-white flex-wrap">
              {([
                { key: "all", label: t("calibration.filterAll"), count: samples.length },
                { key: "unlabeled", label: t("calibration.filterUnlabeled"), count: samples.filter((s) => !s.gold_label).length },
                { key: "labeled", label: t("calibration.filterLabeled"), count: samples.filter((s) => !!s.gold_label).length },
                {
                  key: "mismatch",
                  label: t("calibration.filterMismatch"),
                  count: samples.filter((s) => {
                    const jo = (s.judge_output ?? {}) as Record<string, unknown>;
                    const gold = (s.gold_label ?? null) as Record<string, unknown> | null;
                    if (!gold) return false;
                    const jr = typeof jo.reportable === "boolean" ? jo.reportable : null;
                    const gr = typeof gold.reportable === "boolean" ? gold.reportable : null;
                    return jr !== null && gr !== null && jr !== gr;
                  }).length,
                },
              ] as { key: SampleFilter; label: string; count: number }[]).map(({ key, label, count }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSampleFilter(key)}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs border transition-colors ${sampleFilter === key ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-200 hover:border-gray-400"}`}
                >
                  {label}
                  <span className={`px-1 rounded text-[10px] font-mono ${sampleFilter === key ? "bg-white/20" : "bg-gray-100 text-gray-500"}`}>{count}</span>
                </button>
              ))}
              <div className="relative ml-auto">
                <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="text"
                  value={sampleSearch}
                  onChange={(e) => setSampleSearch(e.target.value)}
                  placeholder={t("calibration.searchPlaceholder")}
                  className="pl-7 pr-2 py-1 text-xs bg-white border border-gray-200 rounded-lg w-52 focus:border-gray-400 focus:outline-none placeholder:text-gray-400"
                />
              </div>
            </div>

            {/* Bulk-action toolbar */}
            <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-100 bg-gray-50/60">
              <input
                type="checkbox"
                checked={filteredSamples.length > 0 && filteredSamples.every((s) => selectedIds.has(s.id))}
                ref={(el) => {
                  // Indeterminate when SOME but not all visible rows are selected.
                  if (!el) return;
                  const visibleSelected = filteredSamples.filter((s) => selectedIds.has(s.id)).length;
                  el.indeterminate = visibleSelected > 0 && visibleSelected < filteredSamples.length;
                }}
                onChange={toggleSelectAll}
                className="accent-gray-900 cursor-pointer"
              />
              <span className="text-xs text-gray-600">
                {selectedIds.size > 0
                  ? t("calibration.selectedCount", { n: selectedIds.size })
                  : t("calibration.selectAll")}
              </span>
              {selectedIds.size > 0 && (
                <button
                  type="button"
                  onClick={() => void handleBatchDelete()}
                  disabled={bulkDeleting}
                  className="ml-auto flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 disabled:opacity-50 transition-colors"
                >
                  {bulkDeleting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                  {t("calibration.deleteSelected", { n: selectedIds.size })}
                </button>
              )}
              <button
                type="button"
                onClick={() => void handleDeleteAll()}
                disabled={bulkDeleting}
                className={`${selectedIds.size > 0 ? "" : "ml-auto"} flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs border border-gray-200 bg-white text-gray-700 hover:border-rose-300 hover:text-rose-700 disabled:opacity-50 transition-colors`}
              >
                {t("calibration.deleteAll")}
              </button>
            </div>
            {filteredSamples.length === 0 && (
              <div className="px-4 py-8 text-center text-xs text-gray-400">
                {t("calibration.noMatchingSamples")}
              </div>
            )}
            <div className="divide-y divide-gray-100">
              {filteredSamples.map((s) => {
                const judgeOutput = (s.judge_output ?? {}) as Record<string, unknown>;
                const judgeVerdict = typeof judgeOutput.verdict_status === "string"
                  ? judgeOutput.verdict_status
                  : "—";
                const gold = (s.gold_label ?? null) as Record<string, unknown> | null;
                const goldVerdict = gold && typeof gold.verdict_status === "string" ? gold.verdict_status : null;
                const isLabeled = gold !== null;
                return (
                  <div key={s.id} className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(s.id)}
                      onChange={() => toggleSelectOne(s.id)}
                      className="accent-gray-900 cursor-pointer shrink-0"
                    />
                    {isLabeled ? (
                      <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-mono text-gray-500 truncate">{s.id}</p>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className="text-[11px] text-gray-500">
                          {t("calibration.judgeSaidLabel")}:{" "}
                          <span className="font-medium text-gray-800 font-mono">{judgeVerdict}</span>
                        </span>
                        {goldVerdict && (
                          <>
                            <span className="text-gray-300">·</span>
                            <span className="text-[11px] text-gray-500">
                              {t("calibration.goldLabelShort")}:{" "}
                              <span className="font-medium text-indigo-700 font-mono">{goldVerdict}</span>
                            </span>
                          </>
                        )}
                        {s.source_type && (
                          <span className="text-[11px] text-gray-400 font-mono">{s.source_type}</span>
                        )}
                      </div>
                    </div>
                    {s.attack_case_id && (
                      <button
                        type="button"
                        onClick={() => setViewing({ caseId: s.attack_case_id!, sample: s })}
                        className="text-xs text-indigo-600 hover:text-indigo-800 shrink-0"
                      >
                        {t("calibration.viewCase")} →
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setLabelingSample(s)}
                      className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs border shrink-0 transition-colors ${isLabeled ? "bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100" : "bg-gray-900 text-white border-gray-900 hover:bg-gray-800"}`}
                    >
                      {isLabeled ? <Pencil className="w-3 h-3" /> : <Tag className="w-3 h-3" />}
                      {isLabeled ? t("calibration.editLabel") : t("calibration.addLabel")}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteSample(s.id)}
                      title={t("calibration.deleteSample")}
                      aria-label={t("calibration.deleteSample")}
                      className="flex items-center justify-center p-1.5 rounded-lg text-rose-500 hover:text-rose-700 hover:bg-rose-50 shrink-0 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {showBatchPanel && (
          <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 space-y-3">
            <p className="text-xs font-semibold text-indigo-800 uppercase tracking-wide">{t("calibration.batchSample")}</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">{t("calibration.batchSampleLimit")}</label>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={batchLimit}
                  onChange={(e) => setBatchLimit(Math.max(1, Math.min(500, Number(e.target.value))))}
                  className="w-full px-3 py-1.5 text-sm bg-white border border-gray-200 rounded-lg text-gray-900 focus:border-indigo-400 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">{t("calibration.batchSampleCategory")}</label>
                <input
                  type="text"
                  value={batchCategory}
                  onChange={(e) => setBatchCategory(e.target.value)}
                  placeholder="prompt_injection"
                  className="w-full px-3 py-1.5 text-sm bg-white border border-gray-200 rounded-lg text-gray-900 placeholder:text-gray-400 focus:border-indigo-400 focus:outline-none font-mono"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={batching}
                onClick={() => void handleBatchSample()}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-indigo-600 text-white text-xs hover:bg-indigo-700 disabled:opacity-60 transition-colors"
              >
                {batching ? t("calibration.batchSampling") : t("calibration.batchSampleRun")}
              </button>
              <button
                type="button"
                onClick={() => setShowBatchPanel(false)}
                className="px-4 py-1.5 rounded-lg border border-gray-200 bg-white text-xs text-gray-700 hover:bg-gray-50 transition-colors"
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Metric cards */}
      {noData ? (
        <div className="card p-8 text-center text-gray-500">
          <p className="font-medium">{t("calibration.noData")}</p>
          <p className="text-sm mt-1">{t("calibration.noDataDesc")}</p>
        </div>
      ) : (
        <>
          {(() => {
            // Compute the "low sample size" flag once so all four metric
            // cards stay in sync. We use the number of samples that were
            // actually evaluable (evaluated = TP+FP+TN+FN), not the raw
            // labeled_count, because samples with a null reportable on
            // either side don't contribute to the rates.
            const evaluatedN = summary!.confusion_matrix?.evaluated ?? summary!.labeled_count;
            const lowSample = evaluatedN > 0 && evaluatedN < LOW_SAMPLE_THRESHOLD;
            const lowLabel = t("calibration.lowSample");
            return (
              <div className="grid grid-cols-4 gap-4">
                <MetricCard
                  label={t("calibration.precisionAtGold")}
                  value={pctLabel(summary!.judge_precision_at_gold)}
                  tone={
                    summary!.judge_precision_at_gold == null ? "text-gray-400"
                    : summary!.judge_precision_at_gold >= 0.8 ? "text-emerald-700"
                    : summary!.judge_precision_at_gold >= 0.6 ? "text-amber-700"
                    : "text-rose-700"
                  }
                  help={t("calibration.precisionHelp")}
                  lowSample={lowSample}
                  lowSampleLabel={lowLabel}
                />
                <MetricCard
                  label={t("calibration.recallAtGold")}
                  value={pctLabel(summary!.judge_recall_at_gold)}
                  tone={
                    summary!.judge_recall_at_gold == null ? "text-gray-400"
                    : summary!.judge_recall_at_gold >= 0.8 ? "text-emerald-700"
                    : summary!.judge_recall_at_gold >= 0.6 ? "text-amber-700"
                    : "text-rose-700"
                  }
                  help={t("calibration.recallHelp")}
                  lowSample={lowSample}
                  lowSampleLabel={lowLabel}
                />
                <MetricCard
                  label={t("calibration.falsePositiveRate")}
                  value={pctLabel(summary!.judge_false_positive_rate)}
                  tone={
                    summary!.judge_false_positive_rate == null ? "text-gray-400"
                    : summary!.judge_false_positive_rate <= 0.1 ? "text-emerald-700"
                    : summary!.judge_false_positive_rate <= 0.25 ? "text-amber-700"
                    : "text-rose-700"
                  }
                  help={t("calibration.fprHelp")}
                  lowSample={lowSample}
                  lowSampleLabel={lowLabel}
                />
                <MetricCard
                  label={t("calibration.overturnRate")}
                  value={pctLabel(summary!.manual_review_overturn_rate)}
                  tone={
                    summary!.manual_review_overturn_rate == null ? "text-gray-400"
                    : summary!.manual_review_overturn_rate <= 0.1 ? "text-emerald-700"
                    : summary!.manual_review_overturn_rate <= 0.25 ? "text-amber-700"
                    : "text-rose-700"
                  }
                  help={t("calibration.overturnHelp")}
                  lowSample={lowSample}
                  lowSampleLabel={lowLabel}
                />
              </div>
            );
          })()}

          {/* Confusion matrix (2×2). Only rendered when at least one sample
              contributed evaluable counts — otherwise the zeros would be
              misleading. */}
          {summary!.confusion_matrix && summary!.confusion_matrix.evaluated > 0 && (
            <ConfusionMatrixCard cm={summary!.confusion_matrix} t={t} />
          )}

          {/* Breakdowns */}
          {(
            [
              { key: "by_category", label: t("calibration.byCategory"), rows: summary!.by_category },
              { key: "by_source_type", label: t("calibration.bySourceType"), rows: summary!.by_source_type },
              { key: "by_business_verification_status", label: t("calibration.byBusinessVerification"), rows: summary!.by_business_verification_status },
            ] as { key: string; label: string; rows: JudgeCalibrationBreakdownItem[] }[]
          ).map(({ key, label, rows }) => (
            <div key={key} className="card overflow-hidden">
              <button
                type="button"
                onClick={() => setExpandedBreakdown(expandedBreakdown === key ? null : key)}
                className="w-full flex items-center justify-between px-4 py-3 text-left text-sm font-semibold text-gray-800 hover:bg-gray-50"
              >
                {label}
                {expandedBreakdown === key ? (
                  <ChevronUp className="w-4 h-4 text-gray-400" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                )}
              </button>
              {expandedBreakdown === key && (
                <div className="p-4">
                  <div className="grid grid-cols-5 gap-2 px-3 pb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
                    <span className="col-span-2">{t("common.name")}</span>
                    <span className="text-center">{t("calibration.sampleCount")}</span>
                    <span className="text-center">{t("calibration.precision")}</span>
                    <span className="text-center">{t("calibration.fpr")}</span>
                  </div>
                  <BreakdownTable rows={rows} />
                </div>
              )}
            </div>
          ))}

          {/* Labeling modal */}
          {/* (rendered outside so the backdrop covers the whole page) */}

          {/* Misclassification preview */}
          {summary!.misclassified_samples.length > 0 && (
            <div className="card overflow-hidden">
              <button
                type="button"
                onClick={() => setExpandedMisclass(!expandedMisclass)}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50"
              >
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-500" />
                  <span className="text-sm font-semibold text-gray-800">
                    {t("calibration.misclassifiedSamples")} ({summary!.misclassified_samples.length})
                  </span>
                </div>
                {expandedMisclass ? (
                  <ChevronUp className="w-4 h-4 text-gray-400" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                )}
              </button>
              {expandedMisclass && (
                <div className="divide-y divide-gray-100">
                  {summary!.misclassified_samples.map((m: JudgeMisclassificationPreview) => (
                    <div key={m.sample_id} className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-gray-50">
                      {m.judge_reportable ? (
                        <XCircle className="w-4 h-4 text-rose-500 shrink-0" />
                      ) : (
                        <CheckCircle className="w-4 h-4 text-amber-500 shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-mono text-gray-500 truncate">{m.sample_id}</p>
                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                          <span className="text-xs text-gray-500">
                            Judge: <span className="font-medium text-gray-800">{m.judge_verdict ?? "—"}</span>
                          </span>
                          <span className="text-gray-300">·</span>
                          <span className="text-xs text-gray-500">
                            Gold: <span className="font-medium text-indigo-700">{m.gold_verdict ?? "—"}</span>
                          </span>
                        </div>
                      </div>
                      <span className={`inline-flex px-2 py-0.5 rounded text-[11px] shrink-0 ${misclassTypeTone(m.mismatch_type)}`}>
                        {m.mismatch_type.replace(/_/g, " ")}
                      </span>
                      {m.attack_case_id && (
                        <button
                          type="button"
                          onClick={() => setViewing({ caseId: m.attack_case_id! })}
                          className="text-xs text-indigo-600 hover:text-indigo-800 shrink-0"
                        >
                          {t("calibration.viewCase")} →
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      <RunsHistoryPanel
        runs={runs}
        loading={loading}
        collapsed={runsCollapsed}
        onToggle={() => setRunsCollapsed((v) => !v)}
        t={t}
      />

      {labelingSample && (
        <GoldLabelModal
          sample={labelingSample}
          onSave={handleSaveLabel}
          onClose={() => setLabelingSample(null)}
          t={t}
        />
      )}

      {/* View-only case detail modal. ``onStartAnnotate`` is only wired
          up when we know the originating sample (i.e. launched from a
          sample row, not from misclassification preview which only has
          a case_id). */}
      {viewing && (
        <CaseDetailOnlyModal
          attackCaseId={viewing.caseId}
          onClose={() => setViewing(null)}
          onStartAnnotate={viewing.sample
            ? () => {
                const s = viewing.sample!;
                setViewing(null);
                setLabelingSample(s);
              }
            : undefined}
          t={t}
        />
      )}
    </div>
  );
}

