/**
 * Display text and pill colors for attack-result fields (verdict, control
 * assessment, quartet variant, business verification, probe summary). Shared
 * by the attack-results page and the report so both read the same.
 */
import type { Translate } from "./labels";

const identity: Translate = (key) => key;

const PILL = {
  emerald: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  teal: "bg-teal-50 text-teal-700 border border-teal-200",
  amber: "bg-amber-50 text-amber-800 border border-amber-200",
  slate: "bg-slate-100 text-slate-700 border border-slate-200",
  rose: "bg-rose-50 text-rose-700 border border-rose-200",
  gray: "bg-gray-100 text-gray-600 border border-gray-200",
  orange: "bg-orange-50 text-orange-900 border border-orange-200",
  sky: "bg-sky-50 text-sky-700 border border-sky-200",
  red: "bg-red-50 text-red-700 border border-red-200",
  fuchsia: "bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200",
} as const;

const VERDICT_KEYS: Record<string, string> = {
  rule_verified: "common.ruleVerified",
  manual_verified: "common.manualVerified",
  ai_suspected: "common.aiSuspected",
  manual_review_needed: "common.manualReviewNeeded",
  false_positive: "common.falsePositive",
  passed: "common.passed",
  not_evaluable: "common.notEvaluable",
};

const VERDICT_TONES: Record<string, string> = {
  rule_verified: PILL.emerald,
  manual_verified: PILL.teal,
  ai_suspected: PILL.amber,
  manual_review_needed: PILL.slate,
  false_positive: PILL.rose,
  passed: PILL.gray,
  not_evaluable: PILL.orange,
};

export function verdictLabel(status?: string | null, t: Translate = identity): string {
  return t(VERDICT_KEYS[status ?? ""] ?? "common.unclassified");
}

export function verdictClasses(status?: string | null): string {
  return VERDICT_TONES[status ?? ""] ?? PILL.gray;
}

const CONTROL_KEYS: Record<string, string> = {
  rule_verified_finding: "common.ruleVerifiedFinding",
  attack_delta_supported: "common.attackDeltaSupported",
  discussion_supported: "common.discussionSupported",
  attack_not_effective: "common.attackNotEffective",
  controls_inconclusive: "common.controlsInconclusive",
  controls_missing: "common.controlsMissing",
  passed: "common.passed",
  not_evaluable: "common.notEvaluable",
};

const CONTROL_TONES: Record<string, string> = {
  rule_verified_finding: PILL.emerald,
  attack_delta_supported: PILL.emerald,
  discussion_supported: PILL.sky,
  controls_inconclusive: PILL.amber,
  not_evaluable: PILL.orange,
};

/** Control-group assessment or case final outcome (they share one vocabulary). */
export function controlLabel(value?: string | null, t: Translate = identity): string {
  return t(CONTROL_KEYS[value ?? ""] ?? "common.controlSummary");
}

export function controlClasses(value?: string | null): string {
  return CONTROL_TONES[value ?? ""] ?? PILL.gray;
}

const VARIANT_KEYS: Record<string, string> = {
  attack: "common.attack",
  clean: "common.clean",
  quoted_attack: "common.quotedAttack",
  benign_distractor: "common.benignDistractor",
};

const VARIANT_TONES: Record<string, string> = {
  attack: PILL.red,
  clean: PILL.emerald,
  quoted_attack: PILL.amber,
  benign_distractor: PILL.sky,
};

export function variantLabel(variantType?: string | null, t: Translate = identity): string {
  const key = VARIANT_KEYS[variantType ?? ""];
  return key ? t(key) : variantType || "—";
}

export function variantClasses(variantType?: string | null): string {
  return VARIANT_TONES[variantType ?? ""] ?? PILL.gray;
}

const BUSINESS_KEYS: Record<string, string> = {
  text_claim_only: "common.textClaimOnly",
  probe_verified: "common.probeVerified",
  probe_failed: "common.probeFailed",
  probe_inconclusive: "common.probeInconclusive",
};

const BUSINESS_TONES: Record<string, string> = {
  text_claim_only: PILL.fuchsia,
  probe_verified: PILL.emerald,
  probe_failed: PILL.rose,
  probe_inconclusive: PILL.amber,
};

/** True when a business-verification probe actually ran or was expected for this result. */
export function hasBusinessVerification(status?: string | null): boolean {
  return !!status && status !== "not_applicable";
}

export function businessVerificationLabel(status?: string | null, t: Translate = identity): string {
  return t(BUSINESS_KEYS[status ?? ""] ?? "common.notApplicable");
}

export function businessVerificationClasses(status?: string | null): string {
  return BUSINESS_TONES[status ?? ""] ?? PILL.gray;
}

type ProbeSummary = Record<string, unknown> | null | undefined;

const numberField = (summary: ProbeSummary, key: string) =>
  typeof summary?.[key] === "number" ? (summary[key] as number) : null;

export function probeFailureType(summary: ProbeSummary): string | null {
  return typeof summary?.["failure_type"] === "string" ? summary["failure_type"] : null;
}

export function probeFailureReason(summary: ProbeSummary): string | null {
  return typeof summary?.["failure_reason"] === "string" ? summary["failure_reason"] : null;
}

/** "1/2 条断言通过 · 1 个步骤", or "" when no probe ran. */
export function probeCountLabel(summary: ProbeSummary, t: Translate = identity): string {
  const verified = numberField(summary, "verified_assertion_count");
  const total = numberField(summary, "total_assertion_count");
  const steps = numberField(summary, "step_count");
  if ((total ?? 0) === 0 && (steps ?? 0) === 0) return "";
  return [
    verified != null && total != null ? t("results.probeAssertions", { verified, total }) : null,
    steps != null ? t("results.probeSteps", { n: steps }) : null,
  ].filter(Boolean).join(" · ");
}

/** "kind @ step" chips from probe evidence lists, de-duplicated across sources. */
export function probeEvidenceChips(...sources: Array<unknown>): string[] {
  const chips: string[] = [];
  for (const source of sources) {
    if (!Array.isArray(source)) continue;
    for (const entry of source) {
      if (!entry || typeof entry !== "object") continue;
      const record = entry as Record<string, unknown>;
      const kind = typeof record["kind"] === "string" ? record["kind"] : "evidence";
      const chip = typeof record["step"] === "string" ? `${kind} @ ${record["step"]}` : kind;
      if (!chips.includes(chip)) chips.push(chip);
    }
  }
  return chips;
}

/** Text color for a 0–1 attack-goal score: higher means the attack got further. */
export function scoreTone(score: number | null | undefined): string {
  if (score == null) return "text-gray-500";
  if (score >= 0.8) return "text-red-600";
  if (score >= 0.5) return "text-orange-600";
  if (score >= 0.2) return "text-amber-700";
  return "text-green-600";
}
