import { useEffect, useState } from "react";
import { GitCompare, ArrowUp, ArrowDown, Plus, Minus, AlertTriangle } from "lucide-react";
import { listScans } from "../api/scans";
import { compareScans, type CompareResult } from "../api/stats";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";
import type { ScanTask } from "../types";

export function Compare() {
  const [scans, setScans] = useState<ScanTask[]>([]);
  const [scanA, setScanA] = useState("");
  const [scanB, setScanB] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();
  const { t } = useLocale();

  useEffect(() => {
    listScans(1, 100, "completed")
      .then((res) => setScans(res.data))
      .catch(() => {});
  }, []);

  async function handleCompare() {
    if (!scanA || !scanB || scanA === scanB) {
      toast("warning", t("compare.selectTwoDifferent"));
      return;
    }
    setLoading(true);
    try {
      const data = await compareScans(scanA, scanB);
      setResult(data);
    } catch (err) {
      toast("error", `Compare failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
        <GitCompare className="w-6 h-6 text-indigo-500" />
        {t("compare.title")}
      </h1>

      <div className="card p-6">
        <div className="grid grid-cols-5 gap-4 items-end">
          <div className="col-span-2">
            <label className="block text-sm text-gray-600 mb-1">{t("compare.baselineScan")}</label>
            <select
              value={scanA}
              onChange={(e) => setScanA(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-gray-200 rounded-lg text-gray-900 text-sm focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10"
            >
              <option value="">{t("compare.selectScan")}</option>
              {scans.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} (Posture: {s.overall_score})
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-center">
            <GitCompare className="w-5 h-5 text-gray-400" />
          </div>
          <div className="col-span-2">
            <label className="block text-sm text-gray-600 mb-1">{t("compare.compareScan")}</label>
            <select
              value={scanB}
              onChange={(e) => setScanB(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-gray-200 rounded-lg text-gray-900 text-sm focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10"
            >
              <option value="">{t("compare.selectScan")}</option>
              {scans.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} (Posture: {s.overall_score})
                </option>
              ))}
            </select>
          </div>
        </div>
        <button
          onClick={handleCompare}
          disabled={loading || !scanA || !scanB}
          className="mt-4 w-full px-4 py-2 bg-gray-900 hover:bg-gray-800 disabled:opacity-50 text-white rounded-xl text-sm font-medium transition-colors"
        >
          {loading ? t("compare.comparing") : t("compare.compareScans")}
        </button>
      </div>

      {result && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <ScoreCard label={result.scan_a.name} score={result.scan_a.overall_score} sublabel="Baseline (A)" />
            <div className="card p-6 flex flex-col items-center justify-center">
              <div
                className={`flex items-center gap-1 text-3xl font-bold ${
                  result.score_diff > 0
                    ? "text-green-600"
                    : result.score_diff < 0
                      ? "text-red-600"
                      : "text-gray-400"
                }`}
              >
                {result.score_diff > 0 ? <ArrowUp className="w-6 h-6" /> : null}
                {result.score_diff < 0 ? <ArrowDown className="w-6 h-6" /> : null}
                {result.score_diff > 0 ? "+" : ""}
                {result.score_diff}
              </div>
              <p className="text-xs text-gray-500 mt-1">{t("compare.postureChange")}</p>
            </div>
            <ScoreCard label={result.scan_b.name} score={result.scan_b.overall_score} sublabel="Compare (B)" />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <VulnList title={t("compare.fixed")} items={result.fixed_vulnerabilities} color="green" icon={Minus} />
            <VulnList title={t("compare.newVulns")} items={result.new_vulnerabilities} color="red" icon={Plus} />
            <VulnList title={t("compare.persistent")} items={result.persistent_vulnerabilities} color="yellow" icon={AlertTriangle} />
          </div>

          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("compare.categoryComparison")}</h2>
            <div className="space-y-3">
              {Object.keys({ ...result.scan_a.categories, ...result.scan_b.categories }).map((cat) => {
                const a = result.scan_a.categories[cat];
                const b = result.scan_b.categories[cat];
                const rateA = a?.rate ?? 0;
                const rateB = b?.rate ?? 0;
                const diff = rateB - rateA;
                return (
                  <div key={cat} className="flex items-center gap-4">
                    <span className="text-sm text-gray-700 w-40 capitalize">{cat.replace(/_/g, " ")}</span>
                    <div className="flex-1 flex items-center gap-2">
                      <span className="text-xs font-mono text-gray-500 w-12 text-right">{rateA}%</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-2 relative">
                        <div className="absolute inset-0 flex">
                          <div className="h-2 rounded-l-full bg-indigo-200" style={{ width: `${rateA}%` }} />
                        </div>
                        <div className="absolute inset-0 flex">
                          <div className="h-2 rounded-l-full bg-indigo-500" style={{ width: `${rateB}%` }} />
                        </div>
                      </div>
                      <span className="text-xs font-mono text-gray-500 w-12">{rateB}%</span>
                    </div>
                    <span
                      className={`text-xs font-mono w-16 text-right ${
                        diff < 0 ? "text-green-600" : diff > 0 ? "text-red-600" : "text-gray-500"
                      }`}
                    >
                      {diff > 0 ? "+" : ""}
                      {diff.toFixed(1)}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ScoreCard({ label, score, sublabel }: { label: string; score: number | null; sublabel: string }) {
  const { t } = useLocale();
  return (
    <div className="card p-6 text-center">
      <p className="text-3xl font-bold text-gray-900">{score ?? "-"}</p>
      <p className="text-sm text-gray-600 mt-1 truncate">{label}</p>
      <p className="text-xs text-gray-400">{sublabel} - {t("compare.postureScore")}</p>
    </div>
  );
}

function VulnList({
  title,
  items,
  color,
  icon: Icon,
}: {
  title: string;
  items: string[];
  color: "green" | "red" | "yellow";
  icon: React.ElementType;
}) {
  const colorMap = {
    green: { text: "text-green-700", bg: "bg-green-50", border: "border-green-200" },
    red: { text: "text-red-700", bg: "bg-red-50", border: "border-red-200" },
    yellow: { text: "text-amber-800", bg: "bg-amber-50", border: "border-amber-200" },
  };
  const c = colorMap[color];

  return (
    <div className={`rounded-xl border p-4 ${c.bg} ${c.border}`}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className={`w-4 h-4 ${c.text}`} />
        <span className={`text-sm font-semibold ${c.text}`}>
          {title} ({items.length})
        </span>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-gray-500">{useLocale().t("common.none")}</p>
      ) : (
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item} className="text-xs text-gray-700 truncate">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

