import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from "recharts";
import type { CategoryScore } from "../../types";
import {
  CHART_AXIS_LABEL_FILL,
  CHART_GRID_STROKE,
  CHART_TICK_FILL,
  chartTooltipContentStyle,
} from "../../utils/chartTheme";

interface Props {
  scores: CategoryScore[];
}

export function CategoryRadarChart({ scores }: Props) {
  if (scores.length < 2) {
    return (
      <div className="h-72 flex items-center justify-center text-gray-500 text-sm">
        Need at least 2 categories for radar chart
      </div>
    );
  }

  const data = scores.map((cs) => ({
    category: cs.category_name,
    score: cs.pass_rate,
    fullMark: 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="72%">
        <PolarGrid stroke={CHART_GRID_STROKE} />
        <PolarAngleAxis dataKey="category" tick={{ fill: CHART_TICK_FILL, fontSize: 11 }} />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: CHART_AXIS_LABEL_FILL, fontSize: 10 }} />
        <Tooltip contentStyle={chartTooltipContentStyle} />
        <Radar
          name="Category Pass Rate"
          dataKey="score"
          stroke="#818cf8"
          fill="#818cf8"
          fillOpacity={0.2}
          strokeWidth={2}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
