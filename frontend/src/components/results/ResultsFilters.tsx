import { Search } from "lucide-react";
import { categoryLabel, type Translate } from "../../utils/labels";
import { businessVerificationLabel } from "../../utils/resultLabels";
import {
  PROBE_FILTERS,
  VERDICT_FILTERS,
  type RowFilters,
  type VerdictFilter,
} from "../../utils/resultRows";

const VERDICT_FILTER_KEYS: Record<VerdictFilter, string> = {
  all: "results.filterAll",
  confirmed: "results.filterConfirmed",
  rule_verified: "results.filterVerified",
  manual_verified: "results.filterManualVerified",
  ai_suspected: "results.filterAiSuspected",
  manual_review_needed: "results.filterNeedsReview",
  false_positive: "results.filterFalsePositive",
  passed: "results.filterPassed",
  not_evaluable: "results.filterNotEvaluable",
};

/**
 * Verdict chips (with counts, so they double as the page summary), search,
 * category, and — only when the scan has any — business-verification states.
 */
export function ResultsFilters({
  filters,
  counts,
  categories,
  showProbeFilter,
  onChange,
  t,
}: {
  filters: RowFilters;
  counts: Record<VerdictFilter, number>;
  categories: string[];
  showProbeFilter: boolean;
  onChange: (next: Partial<RowFilters>) => void;
  t: Translate;
}) {
  // Empty buckets are hidden unless selected; "all" and "confirmed" always show.
  const verdictChips = VERDICT_FILTERS.filter(
    (value) => value === "all" || value === "confirmed" || counts[value] > 0 || filters.verdict === value,
  );

  return (
    <div className="card space-y-3 p-4">
      <div className="flex flex-wrap gap-1.5" role="group" aria-label={t("results.verdictStatus")}>
        {verdictChips.map((value) => {
          const active = filters.verdict === value;
          return (
            <button
              key={value}
              type="button"
              aria-pressed={active}
              onClick={() => onChange({ verdict: value })}
              className={`rounded-md px-3 py-1 text-xs transition-colors ${
                active
                  ? value === "confirmed"
                    ? "border border-orange-200 bg-orange-50 text-orange-800"
                    : "border border-indigo-200 bg-indigo-50 text-indigo-800"
                  : "border border-transparent text-gray-500 hover:text-gray-800"
              }`}
            >
              {t(VERDICT_FILTER_KEYS[value])} <span className="font-mono">{counts[value]}</span>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400" />
          <input
            type="search"
            value={filters.query}
            onChange={(event) => onChange({ query: event.target.value })}
            placeholder={t("results.searchPlaceholder")}
            aria-label={t("results.searchPlaceholder")}
            className="w-full rounded-lg border border-gray-200 bg-white py-1.5 pl-8 pr-3 text-xs text-gray-900 focus:border-gray-900 focus:outline-none"
          />
        </label>
        <select
          value={filters.category}
          onChange={(event) => onChange({ category: event.target.value })}
          aria-label={t("results.allCategories")}
          className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-900 focus:border-gray-900 focus:outline-none"
        >
          <option value="">{t("results.allCategories")}</option>
          {categories.map((category) => (
            <option key={category} value={category}>{categoryLabel(t, category)}</option>
          ))}
        </select>
        {showProbeFilter && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-gray-500">{t("results.businessVerification")}</span>
            {PROBE_FILTERS.map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={filters.probe === value}
                onClick={() => onChange({ probe: value })}
                className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
                  filters.probe === value
                    ? "border border-fuchsia-200 bg-fuchsia-50 text-fuchsia-800"
                    : "border border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                {value === "all" ? t("common.all") : businessVerificationLabel(value, t)}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
