import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { getReport } from "../api/reports";
import { LocaleProvider } from "../i18n";
import type { SecurityReport } from "../types";
import { Report } from "./Report";

vi.mock("../api/reports", () => ({ getReport: vi.fn(), downloadReport: vi.fn() }));
vi.mock("../api/autotest", () => ({ getAutoTestSummary: vi.fn().mockResolvedValue(null), createAutoTestRetestDraft: vi.fn() }));
vi.mock("../components/Toast", () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock("../components/CompliancePanel", () => ({ CompliancePanel: () => null }));

it.each([null, 100])("renders unavailable posture even when legacy score is %s", async (legacyScore) => {
  vi.mocked(getReport).mockResolvedValue({
    scan_id: "fixture", scan_name: "timeout fixture", target_url: "https://fixture.example.com",
    overall_score: legacyScore, security_posture_score: null, risk_level: "unknown",
    total_attacks: 9, completed_attacks: 9, successful_attacks: 0, attack_success_rate: 0,
    evaluable_attack_success_rate: null, evaluable_tests: 0, not_evaluable_tests: 9,
    evaluation_coverage: 0, evaluation_status: "unavailable", average_finding_severity: null,
    average_attack_goal_score: null, average_utility_score: null,
    category_scores: [{
      category: "prompt_injection", category_name: "Fixture category", owasp_id: "LLM01",
      score: null, pass_rate: null, risk_level: "unknown", total_tests: 9,
      successful_attacks: 0, failed_attacks: 0, evaluable_tests: 0,
      not_evaluable_tests: 9, evaluation_coverage: 0,
    }],
  } as unknown as SecurityReport);
  render(
    <LocaleProvider><MemoryRouter initialEntries={["/report/fixture"]}>
      <Routes><Route path="/report/:scanId" element={<Report />} /></Routes>
    </MemoryRouter></LocaleProvider>,
  );
  expect((await screen.findAllByText("无法评分")).length).toBeGreaterThan(0);
  expect(screen.queryByText("SAFE")).not.toBeInTheDocument();
  expect(screen.queryByText("未发现漏洞。")).not.toBeInTheDocument();
  expect(screen.getByText(/评估覆盖率.*0.*0\/9/)).toBeInTheDocument();
  // Category rows use the shared Chinese label, not the server's English name.
  expect(screen.getByText("提示注入")).toBeInTheDocument();
  expect(screen.queryByText("Fixture category")).not.toBeInTheDocument();
  expect(screen.getByText(/无可评样本/)).toBeInTheDocument();
});

it("shows recommendations in Chinese by code and keeps unknown ones as sent", async () => {
  vi.mocked(getReport).mockResolvedValue({
    scan_id: "fixture", scan_name: "codes fixture", target_url: "https://fixture.example.com",
    overall_score: 40, security_posture_score: 40, risk_level: "critical",
    total_attacks: 2, completed_attacks: 2, successful_attacks: 1, attack_success_rate: 50,
    evaluable_attack_success_rate: 50, evaluable_tests: 2, not_evaluable_tests: 0,
    evaluation_coverage: 100, evaluation_status: "complete", average_finding_severity: null,
    average_attack_goal_score: null, average_utility_score: null, category_scores: [],
    recommendations: ["URGENT: Critical vulnerabilities detected.", "A server-only hint."],
    recommendation_codes: ["urgent_critical", "brand_new_code"],
  } as unknown as SecurityReport);
  render(
    <LocaleProvider><MemoryRouter initialEntries={["/report/fixture"]}>
      <Routes><Route path="/report/:scanId" element={<Report />} /></Routes>
    </MemoryRouter></LocaleProvider>,
  );

  expect(await screen.findByText("紧急：检测到严重漏洞，上线前必须立即修复。")).toBeInTheDocument();
  expect(screen.getByText("A server-only hint.")).toBeInTheDocument();
  expect(screen.queryByText("URGENT: Critical vulnerabilities detected.")).not.toBeInTheDocument();
});
