import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { getRiskDistribution, type RiskDistribution } from "../../api/stats";
import { chartLegendTextColor, chartTooltipContentStyle } from "../../utils/chartTheme";
import { useLocale } from "../../i18n";
import { riskLevelLabel } from "../../utils/labels";

const COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#22c55e",
};

export function RiskPieChart() {
  const { t } = useLocale();
  const [data, setData] = useState<RiskDistribution | null>(null);

  useEffect(() => {
    getRiskDistribution().then(setData).catch((e) => console.warn("Failed to load risk distribution:", e));
  }, []);

  if (!data) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
        {t("charts.noVulnerabilityData")}
      </div>
    );
  }

  const total = data.critical + data.high + data.medium + data.low;
  if (total === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
        {t("charts.noVulnerabilities")}
      </div>
    );
  }

  const chartData = (["critical", "high", "medium", "low"] as const)
    .map((level) => ({ level, name: riskLevelLabel(t, level), value: data[level] }))
    .filter((d) => d.value > 0);

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={90}
          paddingAngle={3}
          dataKey="value"
          stroke="none"
        >
          {chartData.map((entry) => (
            <Cell key={entry.level} fill={COLORS[entry.level]} />
          ))}
        </Pie>
        <Tooltip contentStyle={chartTooltipContentStyle} />
        <Legend
          wrapperStyle={{ fontSize: 12 }}
          formatter={(value: string) => <span style={{ color: chartLegendTextColor }}>{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
