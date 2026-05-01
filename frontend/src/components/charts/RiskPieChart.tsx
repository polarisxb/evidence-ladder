import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { getRiskDistribution, type RiskDistribution } from "../../api/stats";
import { chartLegendTextColor, chartTooltipContentStyle } from "../../utils/chartTheme";

const COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#22c55e",
};

export function RiskPieChart() {
  const [data, setData] = useState<RiskDistribution | null>(null);

  useEffect(() => {
    getRiskDistribution().then(setData).catch((e) => console.warn("Failed to load risk distribution:", e));
  }, []);

  if (!data) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
        No vulnerability data
      </div>
    );
  }

  const total = data.critical + data.high + data.medium + data.low;
  if (total === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
        No vulnerabilities found
      </div>
    );
  }

  const chartData = [
    { name: "Critical", value: data.critical },
    { name: "High", value: data.high },
    { name: "Medium", value: data.medium },
    { name: "Low", value: data.low },
  ].filter((d) => d.value > 0);

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
            <Cell key={entry.name} fill={COLORS[entry.name.toLowerCase()]} />
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
