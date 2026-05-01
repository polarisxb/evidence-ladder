import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Shield, Plus, AlertTriangle, CheckCircle, Trash2, Search, TrendingUp, Target, BarChart3 } from "lucide-react";
import { listScans, deleteScan } from "../api/scans";
import { getOverviewStats, type OverviewStats } from "../api/stats";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";
import { ListSkeleton } from "../components/Skeleton";
import { ScoreTrendChart } from "../components/charts/ScoreTrendChart";
import { RiskPieChart } from "../components/charts/RiskPieChart";
import { CategoryBarChart } from "../components/charts/CategoryBarChart";
import { formatDate } from "../utils/format";
import { riskColors, scoreToRisk, riskLabel } from "../utils/risk";
import type { ScanTask } from "../types";

function isReportableScan(scan: ScanTask): boolean {
  return scan.status === "completed" || (
    ["failed", "cancelled"].includes(scan.status) &&
    scan.completed_attacks > 0
  );
}

export function Dashboard() {
  const [scans, setScans] = useState<ScanTask[]>([]);
  const [listTotal, setListTotal] = useState(0);
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const { toast } = useToast();
  const { t } = useLocale();

  const STATUS_OPTIONS = [
    { value: "", label: t("common.all") },
    { value: "completed", label: t("common.completed") },
    { value: "running", label: t("common.running") },
    { value: "pending", label: t("common.pending") },
    { value: "failed", label: t("common.failed") },
    { value: "cancelled", label: t("common.cancelled") },
  ];

  function displayTargetUrl(scan: ScanTask): string {
    if (scan.target_type === "adapter") return `${t("dashboard.adapterTarget")} · ${scan.target_url}`;
    if (scan.target_url.trim()) return scan.target_url;
    if (scan.target_type === "openai_compatible") return t("dashboard.platformDefault");
    if (scan.target_type === "custom") return t("dashboard.legacyCustom");
    return t("dashboard.notConfigured");
  }

  function healthBadge(scan: ScanTask): { label: string; cls: string } | null {
    switch (scan.target_health) {
      case "healthy":
        return { label: t("common.healthy"), cls: "bg-emerald-50 text-emerald-700 border-emerald-200" };
      case "degraded":
        return { label: t("common.degraded"), cls: "bg-amber-50 text-amber-800 border-amber-200" };
      case "unhealthy":
        return { label: t("common.unhealthy"), cls: "bg-rose-50 text-rose-700 border-rose-200" };
      default:
        return null;
    }
  }

  const fetchScans = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listScans(page, pageSize, statusFilter || undefined, searchQuery || undefined);
      setScans(res.data);
      setListTotal(res.total);
    } catch (err) {
      toast("error", `${t("dashboard.failedToLoad")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, searchQuery, page]);

  const fetchOverview = useCallback(async () => {
    try {
      setOverview(await getOverviewStats());
    } catch (err) {
      toast("error", `${t("dashboard.failedToLoadStats")}: ${err instanceof Error ? err.message : err}`);
    }
  }, [toast]);

  useEffect(() => {
    void fetchScans();
  }, [fetchScans]);

  useEffect(() => {
    void fetchOverview();
  }, [fetchOverview]);

  async function handleDelete(e: React.MouseEvent, scanId: string) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(t("dashboard.confirmDelete"))) return;
    try {
      await deleteScan(scanId);
      await Promise.all([fetchScans(), fetchOverview()]);
      toast("success", t("dashboard.deleteSuccess"));
    } catch (err) {
      toast("error", `${t("dashboard.failedToDelete")}: ${err instanceof Error ? err.message : err}`);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearchQuery(searchInput);
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{t("dashboard.title")}</h1>
          <p className="text-gray-500 mt-1 text-sm">{t("dashboard.subtitle")}</p>
        </div>
        <Link
          to="/scan/new"
          className="flex items-center gap-2 px-5 py-2.5 btn-primary rounded-xl text-sm"
        >
          <Plus className="w-4 h-4" />
          {t("dashboard.newScan")}
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="card p-6 glow-border">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-cyan-500/10 flex items-center justify-center">
              <Shield className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <p className="text-3xl font-bold text-gray-900 font-mono">{overview?.total_scans ?? "-"}</p>
              <p className="text-xs text-gray-500 mt-0.5">{t("dashboard.totalScans")}</p>
            </div>
          </div>
        </div>
        <div className="card p-6 glow-border">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-orange-400" />
            </div>
            <div>
              <p className="text-3xl font-bold text-gray-900 font-mono">{overview?.successful_attacks ?? "-"}</p>
              <p className="text-xs text-gray-500 mt-0.5">{t("dashboard.vulnerabilities")}</p>
            </div>
          </div>
        </div>
        <div className="card p-6 glow-border">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <CheckCircle className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <p className="text-3xl font-bold text-gray-900 font-mono">{overview?.completed_scans ?? "-"}</p>
              <p className="text-xs text-gray-500 mt-0.5">{t("dashboard.completedScans")}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-gray-900">{t("dashboard.postureTrend")}</h3>
          </div>
          <ScoreTrendChart />
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-4 h-4 text-orange-400" />
            <h3 className="text-sm font-semibold text-gray-900">{t("dashboard.riskDistribution")}</h3>
          </div>
          <RiskPieChart />
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 className="w-4 h-4 text-red-400" />
            <h3 className="text-sm font-semibold text-gray-900">{t("dashboard.attackSuccessRate")}</h3>
          </div>
          <CategoryBarChart />
        </div>
      </div>

      <div className="card">
        <div className="p-4 border-b border-gray-100 flex items-center gap-4">
          <h2 className="text-lg font-semibold text-gray-900">{t("dashboard.scans")}</h2>

          <div className="flex items-center gap-1 ml-auto">
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setStatusFilter(opt.value)}
                className={`px-3 py-1 text-xs rounded-md transition-colors ${
                  statusFilter === opt.value
                    ? "bg-cyan-50 text-cyan-700"
                    : "text-gray-500 hover:text-gray-800"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder={t("common.search") + "..."}   
                className="pl-9 pr-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg text-gray-900 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10 w-48"
              />
            </div>
          </form>
        </div>

        {loading ? (
          <ListSkeleton rows={5} />
        ) : scans.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            {searchQuery || statusFilter ? (
              <p>{t("common.noResults")}</p>
            ) : (
              <>
                <p>{t("common.noData")}</p>
                <Link to="/scan/new" className="text-indigo-600 hover:underline mt-2 inline-block">
                  {t("dashboard.newScan")}
                </Link>
              </>
            )}
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {scans.map((scan) => {
              const risk = scan.overall_score != null ? scoreToRisk(scan.overall_score) : "none";
              const colors = riskColors[risk];
              const isPartial = scan.status === "completed" && scan.completed_attacks < scan.total_attacks;
              const isRunning = scan.status === "running";
              const pct = isRunning && scan.total_attacks > 0
                ? Math.round((scan.completed_attacks / scan.total_attacks) * 100)
                : 0;
              const health = healthBadge(scan);

              const targetBadge = (() => {
                switch (scan.target_type) {
                  case "adapter": return { label: "Adapter", cls: "bg-sky-50 text-sky-700 border-sky-200" };
                  case "custom": return { label: "Custom", cls: "bg-amber-50 text-amber-800 border-amber-200" };
                  case "openai_compatible": return { label: "OpenAI", cls: "bg-violet-50 text-violet-700 border-violet-200" };
                  default: return { label: t("dashboard.builtin"), cls: "bg-gray-100 text-gray-700 border-gray-200" };
                }
              })();

              return (
                <Link
                  key={scan.id}
                  to={isReportableScan(scan) ? `/report/${scan.id}` : `/scan/${scan.id}`}
                  className="flex items-center justify-between p-4 hover:bg-gray-50/80 hover:shadow-[inset_4px_0_0_#111111] transition-all duration-200"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-gray-900 truncate">{scan.name}</p>
                      <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded border ${targetBadge.cls}`}>
                        {targetBadge.label}
                      </span>
                      {health && (
                        <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded border ${health.cls}`}>
                          {health.label}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 font-mono truncate">{displayTargetUrl(scan)}</p>
                    {(scan.health_failure_reason || scan.invalid_response_ratio != null) && (
                      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                        {scan.invalid_response_ratio != null && (
                          <span>
                            {t("dashboard.invalidRatio")}: {Math.round(scan.invalid_response_ratio * 100)}%
                          </span>
                        )}
                        {scan.health_failure_reason && (
                          <span className="truncate max-w-[420px]">{scan.health_failure_reason}</span>
                        )}
                      </div>
                    )}
                    {isRunning && scan.total_attacks > 0 && (
                      <div className="mt-1.5 flex items-center gap-2">
                        <div className="flex-1 max-w-[180px] bg-gray-100 rounded-full h-1.5">
                          <div
                            className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-[11px] text-indigo-600 font-mono">{pct}%</span>
                      </div>
                    )}
                    {isPartial && (
                      <p className="text-xs text-amber-700 mt-1">
                        {scan.completed_attacks}/{scan.total_attacks} tests
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    {scan.vulnerabilities_found > 0 && (
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-orange-50 text-orange-700 border border-orange-200">
                        <AlertTriangle className="w-3 h-3" />
                        {t("dashboard.vulnBadge", { n: scan.vulnerabilities_found })}
                      </span>
                    )}
                    {scan.overall_score != null && (
                      <span className={`px-2 py-1 rounded text-xs font-mono ${colors.bg} ${colors.text}`}>
                        {riskLabel(risk)} ({scan.overall_score})
                      </span>
                    )}
                    <span className={`text-xs ${isPartial ? "text-amber-700" : isRunning ? "text-indigo-600" : "text-gray-500"}`}>
                      {isPartial ? "partial" : isRunning ? t("dashboard.running") : scan.status}
                    </span>
                    <span className="text-xs text-gray-400">{formatDate(scan.created_at)}</span>
                    {!isRunning && (
                      <button
                        onClick={(e) => handleDelete(e, scan.id)}
                        className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                        title={t("results.deleteScan")}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}

        {listTotal > pageSize && (
          <div className="p-4 border-t border-gray-100 flex items-center justify-between">
            <span className="text-xs text-gray-500">
              {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, listTotal)} / {listTotal}
            </span>
            <div className="flex gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 text-xs bg-white border border-gray-200 rounded disabled:opacity-30 text-gray-600 hover:text-gray-900 hover:border-gray-300 transition-colors"
              >
                {t("dashboard.prev")}
              </button>
              <span className="px-3 py-1 text-xs text-gray-500">
                {page} / {Math.ceil(listTotal / pageSize)}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(Math.ceil(listTotal / pageSize), p + 1))}
                disabled={page >= Math.ceil(listTotal / pageSize)}
                className="px-3 py-1 text-xs bg-white border border-gray-200 rounded disabled:opacity-30 text-gray-600 hover:text-gray-900 hover:border-gray-300 transition-colors"
              >
                {t("dashboard.next")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
