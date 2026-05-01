import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { getCategorySuccessRate, type CategoryRate } from "../../api/stats";
import {
  CHART_AXIS_LABEL_FILL,
  CHART_GRID_STROKE,
  CHART_TICK_FILL,
  chartTooltipContentStyle,
} from "../../utils/chartTheme";

const CATEGORY_LABELS: Record<string, string> = {
  prompt_injection: "Prompt Injection",
  system_prompt_extraction: "Prompt Leakage",
  jailbreak: "Jailbreak",
  information_disclosure: "Info Disclosure",
};

function getBarColor(rate: number): string {
  if (rate >= 60) return "#ef4444";
  if (rate >= 40) return "#f97316";
  if (rate >= 20) return "#eab308";
  return "#22c55e";
}

export function CategoryBarChart() {
  const [data, setData] = useState<CategoryRate[]>([]);

  useEffect(() => {
    getCategorySuccessRate().then(setData).catch((e) => console.warn("Failed to load category rates:", e));
  }, []);

  if (data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
        No attack data yet
      </div>
    );
  }

  const formatted = data.map((d) => ({
    ...d,
    label: CATEGORY_LABELS[d.category] || d.category,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={formatted} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} />
        <XAxis dataKey="label" tick={{ fill: CHART_TICK_FILL, fontSize: 11 }} />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: CHART_TICK_FILL, fontSize: 11 }}
          label={{ value: "Success %", angle: -90, position: "insideLeft", fill: CHART_AXIS_LABEL_FILL, fontSize: 11 }}
        />
        <Tooltip
          contentStyle={chartTooltipContentStyle}
          formatter={(value) => [`${value ?? 0}%`, "Attack Success Rate"]}
        />
        <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
          {formatted.map((entry, i) => (
            <Cell key={i} fill={getBarColor(entry.rate)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
