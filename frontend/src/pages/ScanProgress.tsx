import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, CheckCircle, Loader2 } from "lucide-react";
import { cancelScan, finalizeStuckScan, getScan } from "../api/scans";
import { getAttackResults } from "../api/reports";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";
import { useWebSocket } from "../hooks/useWebSocket";
import { riskColors } from "../utils/risk";
import type { AttackResult, RiskLevel, ScanTask } from "../types";

export function ScanProgress() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [scan, setScan] = useState<ScanTask | null>(null);
  const [attackResults, setAttackResults] = useState<AttackResult[]>([]);
  const [stopping, setStopping] = useState(false);
  const [nowMs, setNowMs] = useState<number>(Date.now());
  const { toast } = useToast();
  const { t } = useLocale();
  const { events } = useWebSocket(taskId);

  const loadAttackResults = useCallback(async () => {
    if (!taskId) return;
    try {
      const rows = await getAttackResults(taskId);
      setAttackResults(rows);
    } catch {
      /* scan may not have persisted rows yet */
    }
  }, [taskId]);

  useEffect(() => {
    if (!taskId) return;
    getScan(taskId)
      .then(setScan)
      .catch((err) => toast("error", `${t("scanProgress.failedToLoad")}: ${err.message}`));
    void loadAttackResults();
  }, [taskId, loadAttackResults, toast]);

  useEffect(() => {
    if (!taskId) return;
    let intervalId: ReturnType<typeof setInterval>;
    const poll = () => {
      getScan(taskId)
        .then((s) => {
          setScan(s);
          void loadAttackResults();
          if (["completed", "failed", "cancelled"].includes(s.status)) {
            clearInterval(intervalId);
          }
        })
        .catch(() => {});
    };
    poll();
    intervalId = setInterval(poll, 2500);
    return () => clearInterval(intervalId);
  }, [taskId, loadAttackResults]);

  useEffect(() => {
    if (!taskId || !scan) return;
    if (scan.total_attacks <= 0) return;
    if (scan.completed_attacks < scan.total_attacks) return;
    if (["completed", "failed", "cancelled"].includes(scan.status)) return;
    const id = setInterval(() => {
      getScan(taskId).then(setScan).catch(() => {});
    }, 800);
    return () => clearInterval(id);
  }, [taskId, scan?.status, scan?.completed_attacks, scan?.total_attacks]);

  useEffect(() => {
    const last = events.at(-1);
    if (last?.type === "attack_completed") {
      void loadAttackResults();
    }
    if (last?.type === "scan_completed" || last?.type === "scan_failed" || last?.type === "scan_health") {
      if (taskId) {
        getScan(taskId).then(setScan).catch(() => {});
      }
    }
  }, [events, loadAttackResults, taskId]);

  // Tick every second so the "attack X has been running for Ns" badges
  // refresh. A single timer is cheaper than per-badge intervals and
  // the UI only cares about 1s resolution. The effect self-disables
  // once the scan is terminal to avoid runaway timers on the Report
  // page (ScanProgress is reused mid-flight and after completion).
  useEffect(() => {
    const terminal =
      scan != null && ["completed", "failed", "cancelled"].includes(scan.status);
    if (terminal) return;
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [scan?.status]);

  const latestProgress = events.filter((e) => e.completed != null).at(-1);
  const completedRaw = latestProgress?.completed ?? scan?.completed_attacks ?? 0;
  const totalRaw = latestProgress?.total ?? scan?.total_attacks ?? 0;
  const total = Math.max(totalRaw, completedRaw);
  const completed = completedRaw;
  const vulns = latestProgress?.vulnerabilities_found ?? scan?.vulnerabilities_found ?? 0;
  const pct = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0;

  const wsCompleted = events.some((e) => e.type === "scan_completed");
  const wsFailed = events.some((e) => e.type === "scan_failed");
  const apiCompleted = scan?.status === "completed";
  const apiFailed = scan?.status === "failed" || scan?.status === "cancelled";
  const scanSucceeded = wsCompleted || apiCompleted;
  const scanEndedEarly = !scanSucceeded && (wsFailed || apiFailed);
  const scanDone = scanSucceeded || scanEndedEarly;
  const doneEvent = events.find((e) => e.type === "scan_completed");
  const finalScore = doneEvent?.overall_score ?? scan?.overall_score ?? undefined;
  const latestHealthEvent = [...events].reverse().find((e) => e.target_health != null);
  const targetHealth = latestHealthEvent?.target_health ?? scan?.target_health ?? null;
  const healthProbePassed = latestHealthEvent?.health_probe_passed ?? scan?.health_probe_passed ?? null;
  const healthReason = latestHealthEvent?.health_failure_reason ?? scan?.health_failure_reason ?? null;
  const recentSignature = latestHealthEvent?.recent_health_signature ?? scan?.recent_health_signature ?? null;
  const invalidRatio = latestHealthEvent?.invalid_response_ratio ?? scan?.invalid_response_ratio ?? null;

  const canStopAndFinalize =
    !scanDone &&
    attackResults.length > 0 &&
    (scan?.status === "running" || scan?.status === "pending");
  const canCancelOnly =
    !scanDone &&
    attackResults.length === 0 &&
    (scan?.status === "running" || scan?.status === "pending");
  const canOpenRecoveredReport =
    attackResults.length > 0 &&
    (scan?.status === "failed" || scan?.status === "cancelled");

  const handleStopAndFinalize = async () => {
    if (!taskId) return;
    setStopping(true);
    try {
      await finalizeStuckScan(taskId);
      const updated = await getScan(taskId);
      setScan(updated);
      toast("success", t("scanProgress.scanStopped"));
      navigate(`/report/${taskId}`);
    } catch (e) {
      toast("error", e instanceof Error ? e.message : t("scanProgress.failedToStop"));
    } finally {
      setStopping(false);
    }
  };

  const handleCancel = async () => {
    if (!taskId) return;
    setStopping(true);
    try {
      await cancelScan(taskId);
      const updated = await getScan(taskId);
      setScan(updated);
      toast("success", t("scanProgress.scanCancelled"));
    } catch (e) {
      toast("error", e instanceof Error ? e.message : t("scanProgress.failedToCancel"));
    } finally {
      setStopping(false);
    }
  };

  const handleOpenRecoveredReport = async () => {
    if (!taskId) return;
    setStopping(true);
    try {
      await finalizeStuckScan(taskId);
      navigate(`/report/${taskId}`);
    } catch (e) {
      toast("error", e instanceof Error ? e.message : t("scanProgress.failedToOpen"));
    } finally {
      setStopping(false);
    }
  };

  const logRows = useMemo(() => {
    const sorted = [...attackResults].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
    return sorted.map((r) => ({
      key: r.id,
      attack_name: r.attack_name,
      successful: r.attack_successful,
      risk_level: r.risk_level,
    }));
  }, [attackResults]);

  // Match attack_started with attack_completed by template_id and keep
  // any still-pending entries. Sorted oldest-first so the list shows the
  // attack that's been stuck the longest at the top — that's usually
  // what the user is wondering about ("why is 11/63 not moving?").
  const runningAttacks = useMemo(() => {
    const pending = new Map<string, { name: string; startedAt: number }>();
    for (const ev of events) {
      if (!ev.template_id) continue;
      if (ev.type === "attack_started" && ev.attack_name) {
        pending.set(ev.template_id, {
          name: ev.attack_name,
          startedAt: ev.received_at ?? Date.now(),
        });
      } else if (ev.type === "attack_completed") {
        pending.delete(ev.template_id);
      }
    }
    return Array.from(pending.entries())
      .map(([id, v]) => ({ id, ...v }))
      .sort((a, b) => a.startedAt - b.startedAt);
  }, [events]);

  const probeRows = useMemo(() => {
    const latest = new Map<string, { caseId: string; state: string }>();
    for (const event of events) {
      if (event.probe_case_id && event.probe_runtime_state) {
        latest.set(event.probe_case_id, {
          caseId: event.probe_case_id,
          state: event.probe_runtime_state,
        });
      }
    }
    return Array.from(latest.values()).slice(-8).reverse();
  }, [events]);

  function probeTone(state: string) {
    switch (state) {
      case "pending":
        return "bg-sky-50 text-sky-700 border border-sky-200";
      case "verified":
        return "bg-emerald-50 text-emerald-700 border border-emerald-200";
      case "failed":
        return "bg-rose-50 text-rose-700 border border-rose-200";
      default:
        return "bg-gray-100 text-gray-600 border border-gray-200";
    }
  }

  function healthTone(state: string | null | undefined) {
    switch (state) {
      case "healthy":
        return "bg-emerald-50 text-emerald-700 border border-emerald-200";
      case "degraded":
        return "bg-amber-50 text-amber-800 border border-amber-200";
      case "unhealthy":
        return "bg-rose-50 text-rose-700 border border-rose-200";
      default:
        return "bg-gray-100 text-gray-600 border border-gray-200";
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">{t("scanProgress.title")}</h1>
      {scan && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span className={`px-2.5 py-1 rounded-full border ${scan.target_type === "adapter" ? "bg-sky-50 text-sky-700 border-sky-200" : scan.target_type === "custom" ? "bg-amber-50 text-amber-800 border-amber-200" : "bg-gray-100 text-gray-700 border-gray-200"}`}>
            {scan.target_type === "adapter" ? t("scanProgress.adapterScan") : scan.target_type === "custom" ? t("scanProgress.legacyCustom") : scan.target_type}
          </span>
          <span className="font-mono text-xs">{scan.target_url}</span>
        </div>
      )}

      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {scanSucceeded ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : scanEndedEarly ? (
              <AlertTriangle className="w-5 h-5 text-amber-600" />
            ) : (
              <Loader2 className="w-5 h-5 text-indigo-500 animate-spin" />
            )}
            <span className="text-gray-900 font-medium">
              {scanSucceeded
                ? t("scanProgress.scanComplete")
                : scanEndedEarly
                ? t("scanProgress.scanEndedEarly")
                : t("scanProgress.scanning")}
            </span>
          </div>
          <span className="text-sm text-gray-500 font-mono">
            {completed}/{total} {t("scanProgress.cases")}
          </span>
        </div>

        <div className="w-full bg-gray-100 rounded-full h-3">
          <div
            className="bg-indigo-500 h-3 rounded-full transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>

        {!scanDone && runningAttacks.length > 0 && (
          <div className="rounded-2xl border border-indigo-100 bg-indigo-50/60 px-4 py-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-indigo-700">
                {t("scanProgress.runningNow")}
              </span>
              <span className="text-xs text-indigo-700">
                {runningAttacks.length}
              </span>
            </div>
            <ul className="space-y-1.5">
              {runningAttacks.slice(0, 6).map((a) => {
                const elapsedS = Math.max(0, Math.round((nowMs - a.startedAt) / 1000));
                const stalled = elapsedS >= 60;
                return (
                  <li
                    key={a.id}
                    className="flex items-center justify-between gap-3 text-sm"
                  >
                    <span className="flex items-center gap-2 min-w-0">
                      <Loader2 className="w-3.5 h-3.5 text-indigo-500 animate-spin shrink-0" />
                      <span className="truncate text-gray-800">{a.name}</span>
                    </span>
                    <span
                      className={`font-mono text-xs shrink-0 ${stalled ? "text-amber-700" : "text-gray-500"}`}
                    >
                      {elapsedS < 60
                        ? `${elapsedS}s`
                        : `${Math.floor(elapsedS / 60)}m ${elapsedS % 60}s`}
                    </span>
                  </li>
                );
              })}
              {runningAttacks.length > 6 && (
                <li className="text-xs text-gray-500">
                  + {runningAttacks.length - 6}
                </li>
              )}
            </ul>
          </div>
        )}

        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold text-gray-900">{pct}%</p>
            <p className="text-xs text-gray-500">{t("scanProgress.progress")}</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-orange-600">{vulns}</p>
            <p className="text-xs text-gray-500">{t("scanProgress.vulnerabilities")}</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900">{completed}</p>
            <p className="text-xs text-gray-500">{t("scanProgress.completed")}</p>
          </div>
        </div>

        {(targetHealth || healthReason || recentSignature || invalidRatio != null) && (
          <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                {t("scanProgress.targetHealth")}
              </span>
              {targetHealth && (
                <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs ${healthTone(targetHealth)}`}>
                  {t(`common.${targetHealth}`)}
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm text-gray-700">
              <div>
                <p className="text-xs text-gray-500">{t("scanProgress.healthProbe")}</p>
                <p className="font-medium">
                  {healthProbePassed == null
                    ? "—"
                    : healthProbePassed
                      ? t("scanProgress.probePassed")
                      : t("scanProgress.probeFailed")}
                </p>
              </div>
              {invalidRatio != null && (
                <div>
                  <p className="text-xs text-gray-500">{t("scanProgress.invalidRatio")}</p>
                  <p className="font-medium">{Math.round(invalidRatio * 100)}%</p>
                </div>
              )}
            </div>
            {recentSignature && (
              <div>
                <p className="text-xs text-gray-500">{t("scanProgress.recentSignature")}</p>
                <p className="font-mono text-xs text-gray-700 break-all">{recentSignature}</p>
              </div>
            )}
            {healthReason && (
              <div>
                <p className="text-xs text-gray-500">{t("scanProgress.healthReason")}</p>
                <p className="text-sm text-gray-700">{healthReason}</p>
              </div>
            )}
          </div>
        )}

        {probeRows.length > 0 && (
          <div className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">{t("scanProgress.probeStatus")}</span>
              <span className="text-xs text-gray-500">{t("scanProgress.runtimeVerification")}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {probeRows.map((row) => (
                <span key={`${row.caseId}-${row.state}`} className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs ${probeTone(row.state)}`}>
                  <span className="font-mono">{row.caseId.slice(0, 8)}</span>
                  <span>{row.state}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {canStopAndFinalize && (
          <button
            type="button"
            disabled={stopping}
            onClick={() => void handleStopAndFinalize()}
            className="w-full mt-4 px-4 py-2 rounded-xl border border-amber-200 bg-amber-50 text-amber-900 hover:bg-amber-100 disabled:opacity-60 transition-colors text-sm"
          >
            {stopping ? t("scanProgress.stopping") : t("scanProgress.stopAndView")}
          </button>
        )}

        {canCancelOnly && (
          <button
            type="button"
            disabled={stopping}
            onClick={() => void handleCancel()}
            className="w-full mt-4 px-4 py-2 rounded-xl border border-gray-200 bg-white text-gray-800 hover:bg-gray-50 disabled:opacity-60 transition-colors text-sm"
          >
            {stopping ? t("scanProgress.cancelling") : t("scanProgress.cancelScan")}
          </button>
        )}

        {canOpenRecoveredReport && (
          <button
            type="button"
            disabled={stopping}
            onClick={() => void handleOpenRecoveredReport()}
            className="w-full mt-4 px-4 py-2 rounded-xl border border-amber-200 bg-amber-50 text-amber-900 hover:bg-amber-100 disabled:opacity-60 transition-colors text-sm"
          >
            {stopping ? t("scanProgress.preparingReport") : t("scanProgress.openPartialReport")}
          </button>
        )}

        {(scan?.status === "completed" || doneEvent) && (
          <button
            onClick={() => navigate(`/report/${taskId}`)}
            className="w-full mt-4 px-4 py-2 bg-gray-900 hover:bg-gray-800 text-white rounded-xl transition-colors"
          >
            {t("scanProgress.viewReport")}
            {finalScore != null ? ` (${t("scanProgress.score")}: ${finalScore})` : ""}
          </button>
        )}
      </div>

      <div className="card overflow-hidden">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">{t("scanProgress.logTitle")}</h2>
        </div>
        <div className="max-h-96 overflow-y-auto divide-y divide-gray-100 font-mono text-sm">
          {logRows.length === 0 ? (
            <div className="p-4 text-gray-500">{t("scanProgress.noAttacks")}</div>
          ) : (
            logRows.map((evt) => {
              const risk = (evt.risk_level || "none") as RiskLevel;
              const colors = riskColors[risk];
              return (
                <div key={evt.key} className="flex items-center gap-3 px-4 py-2 hover:bg-gray-50/80 hover:pl-5 transition-all duration-200">
                  {evt.successful ? (
                    <AlertTriangle className="w-4 h-4 text-orange-500 shrink-0" />
                  ) : (
                    <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />
                  )}
                  <span className="text-gray-700 flex-1 truncate">{evt.attack_name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${colors.bg} ${colors.text}`}>
                    {risk.toUpperCase()}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
