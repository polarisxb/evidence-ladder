import { useEffect, useState } from "react";
import { Shield, CheckCircle, XCircle, Minus } from "lucide-react";
import { getComplianceScore, type ComplianceData } from "../api/stats";

interface Props {
  scanId: string;
}

export function CompliancePanel({ scanId }: Props) {
  const [data, setData] = useState<ComplianceData | null>(null);

  useEffect(() => {
    getComplianceScore(scanId).then(setData).catch((e) => console.warn("Failed to load compliance:", e));
  }, [scanId]);

  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <CoverageCard
          label="OWASP LLM Top 10"
          value={data.owasp_coverage}
          subtitle={`${data.owasp_results.filter((r) => r.tested).length} of ${data.owasp_results.filter((r) => r.testable).length} testable items covered`}
          color="indigo"
        />
        <CoverageCard
          label="MITRE ATLAS"
          value={data.atlas_coverage}
          subtitle={`${data.tested_atlas_ids.length} techniques covered`}
          color="cyan"
        />
      </div>

      <div className="space-y-1">
        {data.owasp_results.map((item) => (
          <div key={item.id} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors">
            <span className="text-xs font-mono text-gray-500 w-14">{item.id}</span>
            <span className="text-sm text-gray-700 flex-1">{item.name}</span>
            {!item.testable ? (
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <Minus className="w-3 h-3" />
                N/A
              </span>
            ) : !item.tested ? (
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <Minus className="w-3 h-3" />
                Not tested
              </span>
            ) : item.failed === 0 ? (
              <span className="flex items-center gap-1 text-xs text-green-400">
                <CheckCircle className="w-3 h-3" />
                {item.score}% pass rate
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs text-red-400">
                <XCircle className="w-3 h-3" />
                {item.failed} finding, {item.score}% pass rate
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function CoverageCard({
  label,
  value,
  subtitle,
  color,
}: {
  label: string;
  value: number;
  subtitle: string;
  color: "indigo" | "cyan";
}) {
  const ringColor = color === "indigo" ? "#818cf8" : "#22d3ee";
  const bgColor = color === "indigo" ? "bg-indigo-500/10 border-indigo-500/20" : "bg-cyan-500/10 border-cyan-500/20";
  const circumference = 2 * Math.PI * 36;
  const offset = circumference * (1 - value / 100);

  return (
    <div className={`flex items-center gap-4 p-4 rounded-xl border ${bgColor}`}>
      <div className="relative w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="36" fill="none" stroke="#e5e5e5" strokeWidth="5" />
          <circle
            cx="40"
            cy="40"
            r="36"
            fill="none"
            stroke={ringColor}
            strokeWidth="5"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 1s ease-out' }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold text-gray-900">{Math.round(value)}%</span>
        </div>
      </div>
      <div>
        <p className="text-sm font-medium text-gray-900 flex items-center gap-1.5">
          <Shield className="w-3.5 h-3.5" />
          {label}
        </p>
        <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
      </div>
    </div>
  );
}
