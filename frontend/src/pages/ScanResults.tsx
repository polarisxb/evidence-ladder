import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, BookOpen, Download } from "lucide-react";
import { getCaseDetail, getScanCases } from "../api/cases";
import { getAttackResults, reviewAttackResult } from "../api/reports";
import { getScan } from "../api/scans";
import { ResultSemanticsCard } from "../components/ResultSemanticsCard";
import { ResultDetail } from "../components/results/ResultDetail";
import { ResultRowItem } from "../components/results/ResultRowItem";
import { ResultsFilters } from "../components/results/ResultsFilters";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";
import type { AttackCase, AttackCaseDetail, AttackResult, ScanTask } from "../types";
import { buildCsvString, downloadCsv } from "../utils/csv";
import { targetTypeLabel } from "../utils/labels";
import { hasBusinessVerification } from "../utils/resultLabels";
import {
  applyReview,
  buildResultRows,
  countVerdicts,
  CSV_HEADERS,
  filterRows,
  normalizeVerdictFilter,
  toCsvRows,
  verdictFilterMatches,
  type ResultRow,
  type ReviewAction,
  type RowFilters,
} from "../utils/resultRows";

const DEFAULT_FILTERS: Omit<RowFilters, "verdict"> = { probe: "all", category: "", query: "" };

/**
 * Attack results of one scan: one row per attack, expanding into its detail.
 *
 * Deep links: `?verdict=<bucket>` (report summary cards) preselects a verdict
 * filter and stays in sync with it; `?case=<attack case id>` (judge
 * calibration) opens and scrolls to that case, and `&back=calibration` makes
 * the back button return there.
 */
export function ScanResults() {
  const { scanId } = useParams<{ scanId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { t } = useLocale();
  const [searchParams, setSearchParams] = useSearchParams();

  const [scan, setScan] = useState<ScanTask | null>(null);
  const [data, setData] = useState<{ cases: AttackCase[]; results: AttackResult[] }>({ cases: [], results: [] });
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<RowFilters>(() => ({
    ...DEFAULT_FILTERS,
    verdict: normalizeVerdictFilter(searchParams.get("verdict")),
  }));
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [details, setDetails] = useState<Record<string, AttackCaseDetail>>({});
  const [detailErrors, setDetailErrors] = useState<Record<string, string>>({});
  const [detailLoading, setDetailLoading] = useState<Set<string>>(new Set());
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [showGuide, setShowGuide] = useState(false);

  useEffect(() => {
    if (!scanId) return;
    setLoading(true);
    Promise.all([
      getScan(scanId).catch(() => null),
      getAttackResults(scanId).catch(() => [] as AttackResult[]),
      getScanCases(scanId).catch(() => [] as AttackCase[]),
    ])
      .then(([scanTask, results, cases]) => {
        setScan(scanTask);
        setData({ cases, results });
      })
      .catch((err) => toast("error", `${t("results.title")}: ${err instanceof Error ? err.message : err}`))
      .finally(() => setLoading(false));
    // Load once per scan; toast/t identity must not trigger a refetch that would wipe local review state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanId]);

  const rows = useMemo(() => buildResultRows(data.cases, data.results), [data]);
  const visibleRows = useMemo(() => filterRows(rows, filters), [rows, filters]);
  const counts = useMemo(() => countVerdicts(rows), [rows]);
  const categories = useMemo(() => [...new Set(rows.map((row) => row.category))], [rows]);
  const showProbeFilter = useMemo(() => rows.some((row) => hasBusinessVerification(row.businessStatus)), [rows]);

  function updateFilters(next: Partial<RowFilters>) {
    setFilters((prev) => ({ ...prev, ...next }));
    if (next.verdict) {
      const verdict = next.verdict;
      setSearchParams((prev) => {
        const params = new URLSearchParams(prev);
        if (verdict === "all") params.delete("verdict");
        else params.set("verdict", verdict);
        return params;
      }, { replace: true });
    }
  }

  async function ensureCaseDetail(caseId: string) {
    if (details[caseId] || detailLoading.has(caseId)) return;
    setDetailLoading((prev) => new Set(prev).add(caseId));
    try {
      const detail = await getCaseDetail(caseId);
      setDetails((prev) => ({ ...prev, [caseId]: detail }));
      setDetailErrors(({ [caseId]: _dropped, ...rest }) => rest);
    } catch (err) {
      setDetailErrors((prev) => ({ ...prev, [caseId]: err instanceof Error ? err.message : String(err) }));
    } finally {
      setDetailLoading((prev) => {
        const next = new Set(prev);
        next.delete(caseId);
        return next;
      });
    }
  }

  function toggleRow(row: ResultRow) {
    const opening = !expanded.has(row.key);
    setExpanded((prev) => {
      const next = new Set(prev);
      if (opening) next.add(row.key);
      else next.delete(row.key);
      return next;
    });
    if (opening && row.attackCase) void ensureCaseDetail(row.attackCase.id);
  }

  // Deep link from judge calibration: open the case once rows are loaded,
  // relaxing a verdict filter that would hide it.
  const deepLinkedCase = useRef<string | null>(null);
  useEffect(() => {
    const caseId = searchParams.get("case");
    if (!caseId || deepLinkedCase.current === caseId || rows.length === 0) return;
    deepLinkedCase.current = caseId;
    const row = rows.find((item) => item.attackCase?.id === caseId);
    if (!row) return;
    if (!verdictFilterMatches(filters.verdict, row.verdict)) setFilters((prev) => ({ ...prev, verdict: "all" }));
    setExpanded((prev) => new Set(prev).add(row.key));
    void ensureCaseDetail(caseId);
    setTimeout(() => document.getElementById(`case-${caseId}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, searchParams]);

  async function handleReview(row: ResultRow, action: ReviewAction) {
    if (!row.resultId) return;
    setReviewingId(row.resultId);
    try {
      const updated = await reviewAttackResult(row.resultId, action);
      setData((prev) => applyReview(prev.cases, prev.results, updated));
      toast("success", t("results.reviewUpdated"));
    } catch (err) {
      toast("error", `${t("results.failedToReview")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setReviewingId(null);
    }
  }

  function handleExport() {
    downloadCsv(`scan-${scanId}-results.csv`, buildCsvString(CSV_HEADERS, toCsvRows(visibleRows)));
  }

  if (loading) return <div className="py-12 text-center text-gray-500">{t("common.loading")}</div>;

  const filtersActive = filters.verdict !== "all" || filters.probe !== "all" || filters.category !== "" || filters.query.trim() !== "";

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-4">
        <button
          type="button"
          onClick={() => (searchParams.get("back") === "calibration" ? navigate(-1) : navigate(`/report/${scanId}`))}
          className="mt-1 text-gray-400 transition-colors hover:text-gray-700"
          aria-label={t("common.back")}
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold text-gray-900">{t("results.title")}</h1>
          {scan && (
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500">
              <span className="font-medium text-gray-700">{scan.name}</span>
              <span className="rounded-full border border-gray-200 bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                {targetTypeLabel(t, scan.target_type)}
              </span>
              <span className="truncate font-mono text-xs">{scan.target_url}</span>
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            aria-pressed={showGuide}
            onClick={() => setShowGuide((open) => !open)}
            className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 transition-colors hover:border-gray-400"
          >
            <BookOpen className="h-3.5 w-3.5" />
            {t("results.guideToggle")}
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={visibleRows.length === 0}
            className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 transition-colors hover:border-gray-400 disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            {t("results.exportCsv")}
          </button>
        </div>
      </div>

      {showGuide && <ResultSemanticsCard t={t} />}

      <ResultsFilters
        filters={filters}
        counts={counts}
        categories={categories}
        showProbeFilter={showProbeFilter}
        onChange={updateFilters}
        t={t}
      />

      <div className="card divide-y divide-gray-100">
        {rows.length === 0 ? (
          <p className="p-8 text-center text-gray-500">{t("results.empty")}</p>
        ) : visibleRows.length === 0 ? (
          <div className="space-y-3 p-8 text-center text-gray-500">
            <p>{t("results.noMatch")}</p>
            {filtersActive && (
              <button
                type="button"
                onClick={() => updateFilters({ ...DEFAULT_FILTERS, verdict: "all" })}
                className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-700 hover:border-gray-400"
              >
                {t("results.clearFilters")}
              </button>
            )}
          </div>
        ) : (
          visibleRows.map((row) => (
            <ResultRowItem key={row.key} row={row} expanded={expanded.has(row.key)} onToggle={() => toggleRow(row)} t={t}>
              <ResultDetail
                row={row}
                detail={row.attackCase ? details[row.attackCase.id] : undefined}
                loading={row.attackCase ? detailLoading.has(row.attackCase.id) : false}
                error={row.attackCase ? detailErrors[row.attackCase.id] : undefined}
                reviewing={reviewingId === row.resultId}
                onReview={(action) => void handleReview(row, action)}
                t={t}
              />
            </ResultRowItem>
          ))
        )}
      </div>
    </div>
  );
}
