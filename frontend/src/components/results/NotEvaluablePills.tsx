import type { Translate } from "../../utils/labels";
import { notEvaluableToneClasses, type NotEvaluableDisplayCategory } from "../../utils/responseEvaluation";

/**
 * Pills for a not-evaluable result: the refined cause ("transport failure",
 * "empty reply · target healthy", …) plus operator hints such as the HTTP
 * status, whether the baseline probe saw the target online, or the matched
 * signature. A bare "not evaluable" label would hide which of those it was.
 */
export function NotEvaluablePills({ category, t }: { category: NotEvaluableDisplayCategory; t: Translate }) {
  const label = t(category.labelKey);
  const hints: string[] = [];
  if (category.httpStatus != null) hints.push(`HTTP ${category.httpStatus}`);
  if (category.probeStatus === "ok") hints.push(t("results.notEvaluableCategory.targetOnline"));
  else if (category.probeStatus === "failed") hints.push(t("results.notEvaluableCategory.targetOffline"));
  if (category.matchedSignature) hints.push(category.matchedSignature);
  const separator = t("results.notEvaluableCategory.suffixSeparator");

  return (
    <>
      <span className={`text-[11px] px-2 py-0.5 rounded ${notEvaluableToneClasses(category.tone)}`}>
        {label !== category.labelKey ? label : category.fallbackLabel}
      </span>
      {hints.length > 0 && (
        <span className="text-[11px] px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200 font-mono">
          {hints.join(` ${separator !== "results.notEvaluableCategory.suffixSeparator" ? separator : "·"} `)}
        </span>
      )}
    </>
  );
}
