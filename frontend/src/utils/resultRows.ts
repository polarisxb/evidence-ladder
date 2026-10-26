/**
 * Row model for the attack-results page.
 *
 * A scan stores each attack twice: an attack case (the quartet unit with its
 * variants) and the attack result the judge scored, linked by
 * `legacy_attack_result_id`. Older scans have results with no case. The page
 * shows one row per attack: every case joined with its result, plus each
 * result no case refers to.
 */
import type { AttackCase, AttackResult } from "../types";
import { resolveResponseEvaluation } from "./responseEvaluation";

export const VERDICT_FILTERS = [
  "all",
  "confirmed",
  "rule_verified",
  "manual_verified",
  "ai_suspected",
  "manual_review_needed",
  "false_positive",
  "passed",
  "not_evaluable",
] as const;
export type VerdictFilter = (typeof VERDICT_FILTERS)[number];
export type Verdict = Exclude<VerdictFilter, "all" | "confirmed">;

export const PROBE_FILTERS = ["all", "text_claim_only", "probe_verified", "probe_failed", "probe_inconclusive"] as const;
export type ProbeFilter = (typeof PROBE_FILTERS)[number];

/** The report's "confirmed findings" bucket. */
const CONFIRMED: ReadonlySet<string> = new Set(["rule_verified", "manual_verified", "ai_suspected"]);
// Verdicts that stand even when the judge did not flag the attack as successful.
const KEPT_WITHOUT_SUCCESS: ReadonlySet<string> = new Set([...CONFIRMED, "manual_review_needed", "false_positive"]);

export function normalizeVerdictFilter(value: string | null): VerdictFilter {
  return (VERDICT_FILTERS as readonly string[]).includes(value ?? "") ? (value as VerdictFilter) : "all";
}

/**
 * The verdict a row shows. A result the judge did not flag is a defense win
 * ("passed") only when no stronger verdict exists; an inconclusive verdict is
 * never collapsed into a pass.
 */
export function resolveVerdict(status: string | null | undefined, successful: boolean | null | undefined): Verdict {
  if (status === "not_evaluable") return "not_evaluable";
  if (!successful) return status && KEPT_WITHOUT_SUCCESS.has(status) ? (status as Verdict) : "passed";
  return (status as Verdict) || "manual_review_needed";
}

export function isConfirmedVerdict(verdict: Verdict): boolean {
  return CONFIRMED.has(verdict);
}

export function verdictFilterMatches(filter: VerdictFilter, verdict: Verdict): boolean {
  if (filter === "all") return true;
  if (filter === "confirmed") return CONFIRMED.has(verdict);
  return filter === verdict;
}

export interface ResultRow {
  /** Case id, or the result id for a result without a case. */
  key: string;
  attackCase: AttackCase | null;
  result: AttackResult | null;
  /** Id the manual-review API takes. */
  resultId: string | null;
  attackName: string;
  category: string;
  technique: string;
  templateId: string;
  verdict: Verdict;
  businessStatus: string | null;
  riskLevel: string | null;
  variantCount: number | null;
  createdAt: string;
}

export function buildResultRows(cases: AttackCase[], results: AttackResult[]): ResultRow[] {
  const resultsById = new Map(results.map((result) => [result.id, result]));
  const linked = new Set<string>();

  const rows: ResultRow[] = cases.map((attackCase) => {
    const result = attackCase.legacy_attack_result_id
      ? resultsById.get(attackCase.legacy_attack_result_id) ?? null
      : null;
    if (result) linked.add(result.id);
    return {
      key: attackCase.id,
      attackCase,
      result,
      resultId: attackCase.legacy_attack_result_id,
      attackName: attackCase.attack_name,
      category: attackCase.category,
      technique: attackCase.technique,
      templateId: attackCase.template_id,
      verdict: resolveVerdict(attackCase.verdict_status, attackCase.primary_attack_successful),
      businessStatus: attackCase.business_verification_status ?? result?.business_verification_status ?? null,
      riskLevel: result?.risk_level ?? null,
      variantCount: attackCase.variant_count,
      createdAt: attackCase.created_at,
    };
  });

  for (const result of results) {
    if (linked.has(result.id)) continue;
    rows.push({
      key: result.id,
      attackCase: null,
      result,
      resultId: result.id,
      attackName: result.attack_name,
      category: result.category,
      technique: result.technique,
      templateId: result.template_id,
      verdict: resolveVerdict(result.verdict_status, result.attack_successful),
      businessStatus: result.business_verification_status ?? null,
      riskLevel: result.risk_level,
      variantCount: null,
      createdAt: result.created_at,
    });
  }
  return rows;
}

export interface RowFilters {
  verdict: VerdictFilter;
  probe: ProbeFilter;
  category: string;
  query: string;
}

export function filterRows(rows: ResultRow[], filters: RowFilters): ResultRow[] {
  const query = filters.query.trim().toLowerCase();
  return rows.filter((row) =>
    verdictFilterMatches(filters.verdict, row.verdict)
    && (filters.probe === "all" || row.businessStatus === filters.probe)
    && (!filters.category || row.category === filters.category)
    && (!query || [row.attackName, row.templateId, row.technique].some((text) => text.toLowerCase().includes(query))),
  );
}

export function countVerdicts(rows: ResultRow[]): Record<VerdictFilter, number> {
  const counts = Object.fromEntries(VERDICT_FILTERS.map((filter) => [filter, 0])) as Record<VerdictFilter, number>;
  for (const row of rows) {
    counts.all += 1;
    counts[row.verdict] += 1;
    if (CONFIRMED.has(row.verdict)) counts.confirmed += 1;
  }
  return counts;
}

export type ReviewAction = "manual_verified" | "false_positive" | "reset";

/**
 * Manual-review actions that change something for this row. Any verdict with
 * a model response can be overridden (the judge can miss in either
 * direction); "reset" only undoes an earlier human override.
 */
export function reviewActionsFor(row: Pick<ResultRow, "resultId" | "verdict">): ReviewAction[] {
  if (!row.resultId || row.verdict === "not_evaluable") return [];
  const actions: ReviewAction[] = [];
  if (row.verdict !== "manual_verified") actions.push("manual_verified");
  if (row.verdict !== "false_positive" && row.verdict !== "passed") actions.push("false_positive");
  if (row.verdict === "manual_verified" || row.verdict === "false_positive") actions.push("reset");
  return actions;
}

/** Apply a reviewed result to the page state: the result itself and the case built on it. */
export function applyReview(
  cases: AttackCase[],
  results: AttackResult[],
  updated: AttackResult,
): { cases: AttackCase[]; results: AttackResult[] } {
  return {
    results: results.map((result) => (result.id === updated.id ? updated : result)),
    cases: cases.map((attackCase) =>
      attackCase.legacy_attack_result_id === updated.id
        ? {
            ...attackCase,
            verdict_status: updated.verdict_status ?? undefined,
            primary_attack_successful: updated.attack_successful,
          }
        : attackCase,
    ),
  };
}

export const CSV_HEADERS = [
  "attack_name", "category", "technique", "template_id",
  "verdict", "attack_successful", "risk_level", "risk_score",
  "case_final_outcome", "control_assessment", "business_verification_status",
  "response_origin", "invalid_reason", "quartet_present", "variant_count",
  "payload_text", "created_at",
];

export function toCsvRows(rows: ResultRow[]): Array<Record<string, unknown>> {
  return rows.map((row) => {
    const { attackCase, result } = row;
    const evaluation = resolveResponseEvaluation(attackCase) ?? resolveResponseEvaluation(result);
    return {
      attack_name: row.attackName,
      category: row.category,
      technique: row.technique,
      template_id: row.templateId,
      verdict: row.verdict,
      attack_successful: result?.attack_successful ?? attackCase?.primary_attack_successful ?? "",
      risk_level: row.riskLevel ?? "",
      risk_score: result?.risk_score ?? "",
      case_final_outcome: attackCase?.case_final_outcome ?? result?.case_final_outcome ?? "",
      control_assessment: attackCase?.control_assessment ?? result?.control_assessment ?? "",
      business_verification_status: row.businessStatus ?? "",
      response_origin: evaluation?.response_origin ?? "",
      invalid_reason: evaluation?.invalid_reason ?? "",
      quartet_present: attackCase?.quartet_present ?? result?.quartet_present ?? "",
      variant_count: row.variantCount ?? "",
      payload_text: result?.payload_text ?? "",
      created_at: row.createdAt,
    };
  });
}
