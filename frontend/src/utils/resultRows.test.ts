import { describe, expect, it } from "vitest";
import { makeCase, makeResult } from "../test/resultFixtures";
import {
  applyReview,
  buildResultRows,
  countVerdicts,
  CSV_HEADERS,
  filterRows,
  normalizeVerdictFilter,
  resolveVerdict,
  reviewActionsFor,
  toCsvRows,
} from "./resultRows";

describe("resolveVerdict", () => {
  it("never turns an inconclusive verdict into a defense win", () => {
    expect(resolveVerdict("manual_review_needed", false)).toBe("manual_review_needed");
    expect(resolveVerdict("ai_suspected", false)).toBe("ai_suspected");
    expect(resolveVerdict(null, false)).toBe("passed");
    expect(resolveVerdict(null, true)).toBe("manual_review_needed");
    expect(resolveVerdict("not_evaluable", true)).toBe("not_evaluable");
  });

  it("falls back to all for unknown deep-link filters", () => {
    expect(normalizeVerdictFilter("confirmed")).toBe("confirmed");
    expect(normalizeVerdictFilter("bogus")).toBe("all");
    expect(normalizeVerdictFilter(null)).toBe("all");
  });
});

describe("buildResultRows", () => {
  const cases = [
    makeCase({ id: "case-1", legacy_attack_result_id: "result-1" }),
    makeCase({
      id: "case-2", legacy_attack_result_id: "result-2", attack_name: "Leak", category: "information_disclosure",
      template_id: "ID-002", verdict_status: "rule_verified", primary_attack_successful: true,
      business_verification_status: "probe_verified",
    }),
  ];
  const results = [
    makeResult({ id: "result-1" }),
    makeResult({ id: "result-2", attack_successful: true, risk_level: "high", risk_score: 7.5 }),
    makeResult({ id: "orphan", attack_name: "Old scan attack", template_id: "JB-009", category: "jailbreak", verdict_status: "ai_suspected", attack_successful: true }),
  ];

  it("joins each case with its result and keeps results no case refers to", () => {
    const rows = buildResultRows(cases, results);

    expect(rows.map((row) => row.key)).toEqual(["case-1", "case-2", "orphan"]);
    expect(rows[1]).toMatchObject({ verdict: "rule_verified", riskLevel: "high", businessStatus: "probe_verified", variantCount: 4 });
    expect(rows[1].result?.id).toBe("result-2");
    expect(rows[2]).toMatchObject({ attackCase: null, resultId: "orphan", verdict: "ai_suspected", variantCount: null });
  });

  it("counts verdicts once per attack, with confirmed as the report's composite bucket", () => {
    const counts = countVerdicts(buildResultRows(cases, results));

    expect(counts).toMatchObject({ all: 3, confirmed: 2, rule_verified: 1, ai_suspected: 1, passed: 1, manual_review_needed: 0 });
  });

  it("filters by verdict, business verification, category and free text", () => {
    const rows = buildResultRows(cases, results);
    const base = { verdict: "all", probe: "all", category: "", query: "" } as const;

    expect(filterRows(rows, { ...base, verdict: "confirmed" }).map((row) => row.key)).toEqual(["case-2", "orphan"]);
    expect(filterRows(rows, { ...base, probe: "probe_verified" }).map((row) => row.key)).toEqual(["case-2"]);
    expect(filterRows(rows, { ...base, category: "jailbreak" }).map((row) => row.key)).toEqual(["orphan"]);
    expect(filterRows(rows, { ...base, query: "id-002" }).map((row) => row.key)).toEqual(["case-2"]);
    expect(filterRows(rows, { ...base, query: "Direct" }).map((row) => row.key)).toEqual(["case-1"]);
    // Technique is searchable too, and every fixture shares this one.
    expect(filterRows(rows, { ...base, query: "instruction_override" })).toHaveLength(3);
  });
});

describe("manual review", () => {
  it("offers the overrides that change something, and reset only after an override", () => {
    expect(reviewActionsFor({ resultId: "r", verdict: "manual_review_needed" })).toEqual(["manual_verified", "false_positive"]);
    expect(reviewActionsFor({ resultId: "r", verdict: "passed" })).toEqual(["manual_verified"]);
    expect(reviewActionsFor({ resultId: "r", verdict: "manual_verified" })).toEqual(["false_positive", "reset"]);
    expect(reviewActionsFor({ resultId: "r", verdict: "false_positive" })).toEqual(["manual_verified", "reset"]);
    expect(reviewActionsFor({ resultId: "r", verdict: "not_evaluable" })).toEqual([]);
    expect(reviewActionsFor({ resultId: null, verdict: "ai_suspected" })).toEqual([]);
  });

  it("updates the reviewed result and the case built on it", () => {
    const cases = [makeCase({ id: "case-1", legacy_attack_result_id: "result-1" }), makeCase({ id: "case-x", legacy_attack_result_id: "result-x" })];
    const results = [makeResult({ id: "result-1" }), makeResult({ id: "result-x" })];
    const updated = makeResult({ id: "result-1", verdict_status: "manual_verified", attack_successful: true });

    const next = applyReview(cases, results, updated);

    expect(next.results[0]).toBe(updated);
    expect(next.cases[0]).toMatchObject({ verdict_status: "manual_verified", primary_attack_successful: true });
    expect(next.cases[1]).toBe(cases[1]);
    expect(buildResultRows(next.cases, next.results)[0].verdict).toBe("manual_verified");
  });
});

describe("toCsvRows", () => {
  it("exports one line per attack with case and result fields together", () => {
    const rows = buildResultRows(
      [makeCase({ id: "case-1", legacy_attack_result_id: "result-1", case_final_outcome: "attack_delta_supported" })],
      [makeResult({ id: "result-1", risk_level: "medium", risk_score: 5.5 })],
    );

    const [line] = toCsvRows(rows);

    expect(Object.keys(line)).toEqual(CSV_HEADERS);
    expect(line).toMatchObject({
      template_id: "PI-001", verdict: "passed", risk_level: "medium", risk_score: 5.5,
      case_final_outcome: "attack_delta_supported", variant_count: 4, payload_text: "ignore all previous instructions",
    });
  });
});
