import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { getCategorySuccessRate, type CategoryRate } from "../../api/stats";
import { useLocale } from "../../i18n";
import { categoryLabel } from "../../utils/labels";
import {
  CHART_AXIS_LABEL_FILL,
  CHART_GRID_STROKE,
  CHART_TICK_FILL,
  chartTooltipContentStyle,
} from "../../utils/chartTheme";

function getBarColor(rate: number | null): string {
  if (rate == null) return "#94a3b8";
  if (rate >= 60) return "#ef4444";
  if (rate >= 40) return "#f97316";
  if (rate >= 20) return "#eab308";
  return "#22c55e";
}

export function CategoryBarChart() {
  const { t } = useLocale();
  const [data, setData] = useState<CategoryRate[]>([]);

  useEffect(() => {
    getCategorySuccessRate().then(setData).catch((e) => console.warn("Failed to load category rates:", e));
  }, []);

  if (data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 text-sm">
        {t("charts.noAttackData")}
      </div>
    );
  }

  if (data.every((entry) => entry.rate == null)) {
    return <div className="h-64 flex items-center justify-center text-gray-500 text-sm">{t("charts.noEvaluableResults")}</div>;
  }

  const formatted = data.map((d) => ({
    ...d,
    label: categoryLabel(t, d.category),
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={formatted} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} />
        {/* Every category gets a label; tilt them so long names do not collide. */}
        <XAxis dataKey="label" interval={0} angle={-25} textAnchor="end" height={56} tick={{ fill: CHART_TICK_FILL, fontSize: 11 }} />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: CHART_TICK_FILL, fontSize: 11 }}
          label={{ value: t("charts.successPct"), angle: -90, position: "insideLeft", fill: CHART_AXIS_LABEL_FILL, fontSize: 11 }}
        />
        <Tooltip
          contentStyle={chartTooltipContentStyle}
          formatter={(value) => [value == null ? "—" : `${value}%`, t("charts.attackSuccessRate")]}
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
