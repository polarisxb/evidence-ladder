import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { getScoreTrend, type ScoreTrendPoint } from "../../api/stats";
import {
  CHART_GRID_STROKE,
  CHART_TICK_FILL,
  chartTooltipContentStyle,
  chartTooltipLabelStyle,
} from "../../utils/chartTheme";

export function ScoreTrendChart() {
  const [data, setData] = useState<ScoreTrendPoint[]>([]);

  useEffect(() => {
    getScoreTrend().then(setData).catch((e) => console.warn("Failed to load score trend:", e));
  }, []);

  if (data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
        No scan data yet
      </div>
    );
  }

  const formatted = data.map((d) => ({
    ...d,
    label: d.name.length > 12 ? d.name.slice(0, 12) + "..." : d.name,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={formatted} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} />
        <XAxis dataKey="label" tick={{ fill: CHART_TICK_FILL, fontSize: 11 }} />
        <YAxis domain={[0, 100]} tick={{ fill: CHART_TICK_FILL, fontSize: 11 }} />
        <Tooltip contentStyle={chartTooltipContentStyle} labelStyle={chartTooltipLabelStyle} />
        <ReferenceLine y={90} stroke="#22c55e" strokeDasharray="3 3" label={{ value: "LOW", fill: "#22c55e", fontSize: 10 }} />
        <ReferenceLine y={70} stroke="#eab308" strokeDasharray="3 3" label={{ value: "MED", fill: "#eab308", fontSize: 10 }} />
        <ReferenceLine y={50} stroke="#f97316" strokeDasharray="3 3" label={{ value: "HIGH", fill: "#f97316", fontSize: 10 }} />
        <Line
          type="monotone"
          dataKey="score"
          name="Security Posture Score"
          stroke="#818cf8"
          strokeWidth={2}
          dot={{ fill: "#818cf8", r: 4 }}
          activeDot={{ r: 6 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
