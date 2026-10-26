import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle, ChevronDown, ChevronUp, HelpCircle, MinusCircle } from "lucide-react";
import type { RiskLevel } from "../../types";
import { categoryLabel, riskLevelLabel, type Translate } from "../../utils/labels";
import {
  businessVerificationClasses,
  businessVerificationLabel,
  hasBusinessVerification,
  verdictClasses,
  verdictLabel,
} from "../../utils/resultLabels";
import { isConfirmedVerdict, type ResultRow } from "../../utils/resultRows";
import { notEvaluableDisplayCategory, resolveResponseEvaluation } from "../../utils/responseEvaluation";
import { riskColors } from "../../utils/risk";
import { NotEvaluablePills } from "./NotEvaluablePills";

function VerdictIcon({ row }: { row: ResultRow }) {
  if (isConfirmedVerdict(row.verdict)) return <AlertTriangle className="h-4 w-4 shrink-0 text-red-500" />;
  if (row.verdict === "manual_review_needed") return <HelpCircle className="h-4 w-4 shrink-0 text-amber-500" />;
  if (row.verdict === "not_evaluable") return <MinusCircle className="h-4 w-4 shrink-0 text-gray-400" />;
  return <CheckCircle className="h-4 w-4 shrink-0 text-green-600" />;
}

/** One attack: a summary line that expands into its detail. */
export function ResultRowItem({
  row,
  expanded,
  onToggle,
  t,
  children,
}: {
  row: ResultRow;
  expanded: boolean;
  onToggle: () => void;
  t: Translate;
  children?: ReactNode;
}) {
  const notEvaluable = row.verdict === "not_evaluable"
    ? notEvaluableDisplayCategory(resolveResponseEvaluation(row.attackCase) ?? resolveResponseEvaluation(row.result))
    : null;
  const risk = row.riskLevel as RiskLevel | null;
  const showRisk = isConfirmedVerdict(row.verdict) && risk != null && risk !== "none" && risk !== "unknown";

  return (
    <div id={`case-${row.key}`} className="scroll-mt-4">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={onToggle}
        className="flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-gray-50"
      >
        <VerdictIcon row={row} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm text-gray-900">{row.attackName}</p>
          <p className="truncate text-xs text-gray-500">
            {categoryLabel(t, row.category)}
            <span className="mx-1.5 text-gray-300">·</span>
            <span className="font-mono">{row.templateId}</span>
          </p>
        </div>
        {hasBusinessVerification(row.businessStatus) && (
          <span className={`shrink-0 rounded px-2 py-0.5 text-[11px] ${businessVerificationClasses(row.businessStatus)}`}>
            {businessVerificationLabel(row.businessStatus, t)}
          </span>
        )}
        {showRisk && (
          <span className={`shrink-0 rounded px-2 py-0.5 text-[11px] ${riskColors[risk!].bg} ${riskColors[risk!].text}`}>
            {riskLevelLabel(t, risk)}
          </span>
        )}
        {notEvaluable ? (
          <NotEvaluablePills category={notEvaluable} t={t} />
        ) : (
          <span className={`shrink-0 rounded px-2 py-0.5 text-[11px] ${verdictClasses(row.verdict)}`}>
            {verdictLabel(row.verdict, t)}
          </span>
        )}
        <span className="w-16 shrink-0 text-right text-[11px] text-gray-400">
          {row.variantCount != null ? t("results.variantCount", { n: row.variantCount }) : t("results.noCaseRecord")}
        </span>
        {expanded ? <ChevronUp className="h-4 w-4 shrink-0 text-gray-400" /> : <ChevronDown className="h-4 w-4 shrink-0 text-gray-400" />}
      </button>
      {expanded && <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-4 sm:px-11">{children}</div>}
    </div>
  );
}
