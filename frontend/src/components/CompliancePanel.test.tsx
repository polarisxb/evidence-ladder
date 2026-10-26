import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { getComplianceScore } from "../api/stats";
import { LocaleProvider } from "../i18n";
import { CompliancePanel } from "./CompliancePanel";

vi.mock("../api/stats", () => ({ getComplianceScore: vi.fn() }));

it("shows unassessed coverage instead of an empty green pass rate", async () => {
  vi.mocked(getComplianceScore).mockResolvedValue({
    owasp_coverage: 20, atlas_coverage: 10, tested_atlas_ids: [], overall_score: null,
    owasp_results: [{
      id: "LLM01", name: "fixture category", tested: true, testable: true,
      total_tests: 9, evaluable: 0, not_evaluable: 9, passed: 0, failed: 0, score: null,
    }],
  });
  render(<LocaleProvider><CompliancePanel scanId="fixture" /></LocaleProvider>);
  expect(await screen.findByText("无法评估")).toBeInTheDocument();
  expect(screen.queryByText(/通过率/)).not.toBeInTheDocument();
  expect(screen.getByText("9 条不可评估")).toBeInTheDocument();
});

it("names OWASP items and coverage in Chinese", async () => {
  vi.mocked(getComplianceScore).mockResolvedValue({
    owasp_coverage: 40, atlas_coverage: 10, tested_atlas_ids: ["AML.T0051", "AML.T0054"], overall_score: 80,
    owasp_results: [
      { id: "LLM01", name: "Prompt Injection", tested: true, testable: true,
        total_tests: 4, evaluable: 4, not_evaluable: 0, passed: 3, failed: 1, score: 75 },
      { id: "LLM03", name: "Supply Chain Vulnerabilities", tested: false, testable: false,
        total_tests: 0, evaluable: 0, not_evaluable: 0, passed: 0, failed: 0, score: null },
    ],
  });
  render(<LocaleProvider><CompliancePanel scanId="fixture" /></LocaleProvider>);

  expect(await screen.findByText("提示词注入")).toBeInTheDocument();
  expect(screen.getByText("供应链漏洞")).toBeInTheDocument();
  expect(screen.getByText("1 个问题，通过率 75%")).toBeInTheDocument();
  expect(screen.getByText("不适用")).toBeInTheDocument();
  expect(screen.getByText("可测试的 1 项中已覆盖 1 项")).toBeInTheDocument();
  expect(screen.getByText("已覆盖 2 项攻击技术")).toBeInTheDocument();
});
