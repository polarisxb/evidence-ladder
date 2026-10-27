import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { createAutoTestDraft } from "../api/autotest";
import type { AutoTestDraft } from "../types";
import { LocaleProvider } from "../i18n";
import { AutoTest } from "./AutoTest";

const { toast } = vi.hoisted(() => ({ toast: vi.fn() }));
vi.mock("../components/Toast", () => ({ useToast: () => ({ toast }) }));
vi.mock("../api/adapters", () => ({ getAdapters: vi.fn().mockResolvedValue([]) }));
vi.mock("../api/scans", () => ({ createScan: vi.fn() }));
vi.mock("../api/autotest", () => ({ createAutoTestDraft: vi.fn() }));

const DRAFT = {
  plan: {
    target_type: "openai_compatible", budget: "medium", risk_categories: ["jailbreak"],
    strategies: ["template"], phases: ["template_scan"], probe_available: false, max_retest_rounds: 1,
  },
  scan_config: {
    name: "draft", target_type: "openai_compatible", target_url: "", attack_categories: ["jailbreak"],
    advanced: { quartet_mode: "adaptive", parallel_attacks: 3, retest_arm: "B", max_retest_rounds: 1 },
  },
} as unknown as AutoTestDraft;

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(createAutoTestDraft).mockResolvedValue(DRAFT);
});

it("leaves the retest budget to the planner by default and shows the retest in the draft", async () => {
  render(<LocaleProvider><MemoryRouter><AutoTest /></MemoryRouter></LocaleProvider>);
  fireEvent.click(screen.getByRole("button", { name: /生成草稿/ }));

  await waitFor(() => expect(createAutoTestDraft).toHaveBeenCalled());
  expect(vi.mocked(createAutoTestDraft).mock.calls[0][0].max_retest_rounds).toBeNull();
  expect(await screen.findByText("冲突补测 ×1")).toBeInTheDocument();
  expect(screen.getByText("模板扫描")).toBeInTheDocument();
  // Once as the selected target-type option, once as the draft pill.
  expect(screen.getAllByText("OpenAI 兼容")).toHaveLength(2);
});

it("can switch the in-scan retest off", async () => {
  render(<MemoryRouter><AutoTest /></MemoryRouter>);
  fireEvent.change(screen.getByDisplayValue("autotest.retestRoundsDefault"), { target: { value: "0" } });
  fireEvent.click(screen.getByRole("button", { name: /autotest\.generateDraft/ }));

  await waitFor(() => expect(createAutoTestDraft).toHaveBeenCalled());
  expect(vi.mocked(createAutoTestDraft).mock.calls[0][0].max_retest_rounds).toBe(0);
});
