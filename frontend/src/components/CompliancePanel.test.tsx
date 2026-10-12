import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { getComplianceScore } from "../api/stats";
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
  render(<CompliancePanel scanId="fixture" />);
  expect(await screen.findByText("Unable to assess")).toBeInTheDocument();
  expect(screen.queryByText(/% pass rate/)).not.toBeInTheDocument();
  expect(screen.getByText("9 not evaluable")).toBeInTheDocument();
});
