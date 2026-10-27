import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { listScans } from "../api/scans";
import { LocaleProvider } from "../i18n";
import type { ScanTask } from "../types";
import { Dashboard } from "./Dashboard";

vi.mock("../components/Toast", () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock("../api/scans", () => ({ listScans: vi.fn(), deleteScan: vi.fn() }));
vi.mock("../api/stats", () => ({
  getOverviewStats: vi.fn().mockResolvedValue({
    total_scans: 4, completed_scans: 2, total_attacks: 10, successful_attacks: 1, avg_score: 50, attack_success_rate: 10,
  }),
  getScoreTrend: vi.fn().mockResolvedValue([]),
  getRiskDistribution: vi.fn().mockResolvedValue({ critical: 0, high: 0, medium: 0, low: 0 }),
  getCategorySuccessRate: vi.fn().mockResolvedValue([]),
}));

const LONG_AGO = "2026-01-01T00:00:00Z";

function scan(overrides: Partial<ScanTask>): ScanTask {
  return {
    id: overrides.name ?? "scan", name: "scan", status: "completed", target_url: "https://fixture.example.com",
    target_type: "openai_compatible", attack_categories: ["jailbreak"], total_attacks: 5, completed_attacks: 5,
    vulnerabilities_found: 0, overall_score: 80, started_at: null, completed_at: null,
    created_at: LONG_AGO, updated_at: LONG_AGO, ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(listScans).mockResolvedValue({
    data: [
      scan({ name: "claude-target", target_type: "claude", overall_score: 30 }),
      scan({ name: "orphaned", target_type: "builtin_vulnerable", status: "pending", overall_score: null, runner_active: false }),
      scan({ name: "partial-run", target_type: "custom", completed_attacks: 3, total_attacks: 5, overall_score: 95 }),
      scan({ name: "live", status: "running", overall_score: null, runner_active: true, completed_attacks: 1 }),
    ],
    total: 4,
  } as Awaited<ReturnType<typeof listScans>>);
});

function row(name: string) {
  return screen.getByText(name).closest("a") as HTMLElement;
}

it("labels a Claude target as Claude, not as a built-in target", async () => {
  render(<LocaleProvider><MemoryRouter><Dashboard /></MemoryRouter></LocaleProvider>);
  await screen.findByText("claude-target");

  expect(within(row("claude-target")).getByText("Claude")).toBeInTheDocument();
  expect(within(row("claude-target")).queryByText("内置靶场")).not.toBeInTheDocument();
  expect(within(row("orphaned")).getByText("内置靶场")).toBeInTheDocument();
  expect(within(row("partial-run")).getByText("自定义 HTTP")).toBeInTheDocument();
});

it("shows scan states and risk levels in Chinese", async () => {
  render(<LocaleProvider><MemoryRouter><Dashboard /></MemoryRouter></LocaleProvider>);
  await screen.findByText("claude-target");

  expect(within(row("claude-target")).getByText("已完成")).toBeInTheDocument();
  expect(within(row("claude-target")).getByText("严重 (30)")).toBeInTheDocument();
  expect(within(row("orphaned")).getByText("已中断")).toBeInTheDocument();
  expect(within(row("partial-run")).getByText("部分完成")).toBeInTheDocument();
  expect(within(row("partial-run")).getByText("已完成 3/5 项测试")).toBeInTheDocument();
  expect(within(row("live")).getByText("运行中")).toBeInTheDocument();
  for (const raw of ["pending", "completed", "partial", "CRITICAL"]) {
    expect(screen.queryByText(raw)).not.toBeInTheDocument();
  }
});
