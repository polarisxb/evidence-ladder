import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { getAdapters, installSampleAdapter } from "../api/adapters";
import { createScan } from "../api/scans";
import { listMockTargets } from "../api/targets";
import type { Adapter, ScanConfig } from "../types";
import { NewScan } from "./NewScan";

const { toast } = vi.hoisted(() => ({ toast: vi.fn() }));
vi.mock("../components/Toast", () => ({ useToast: () => ({ toast }) }));
vi.mock("../api/settings", () => ({
  getSettings: vi.fn().mockResolvedValue({ openai_model: "deepseek-v4-flash", openai_api_key_set: true }),
}));
vi.mock("../api/modelProviders", () => ({
  listModelProviders: vi.fn().mockResolvedValue([]),
  fetchProviderModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("../api/client", () => ({ request: vi.fn().mockResolvedValue({ data: [] }) }));
vi.mock("../api/adapters", () => ({ getAdapters: vi.fn(), installSampleAdapter: vi.fn() }));
vi.mock("../api/scans", () => ({ createScan: vi.fn() }));
vi.mock("../api/targets", () => ({ listMockTargets: vi.fn() }));

const MAILBOT_ADAPTER = {
  id: "adapter-mailbot", name: "mailbot-agent", transport: "http_json", enabled: true,
  base_url: "http://localhost:8003",
} as Adapter;

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getAdapters).mockResolvedValue([]);
  vi.mocked(installSampleAdapter).mockResolvedValue({ adapter: MAILBOT_ADAPTER, created: true });
  vi.mocked(createScan).mockResolvedValue({ task_id: "task-1" });
  vi.mocked(listMockTargets).mockResolvedValue([
    { key: "financebot", base_url: "http://financebot:8001", chat_url: "http://financebot:8001/chat", sample_adapter: null },
  ]);
});

function renderPage() {
  return render(<MemoryRouter><NewScan /></MemoryRouter>);
}

function submittedConfig(): ScanConfig {
  expect(createScan).toHaveBeenCalledTimes(1);
  return vi.mocked(createScan).mock.calls[0][0];
}

it("sends the conflict-retest arm and health thresholds chosen in advanced options", async () => {
  renderPage();
  fireEvent.click(screen.getByText("newScan.advancedModes"));
  fireEvent.click(screen.getByRole("button", { name: "newScan.retestArmB" }));
  fireEvent.change(screen.getByLabelText("newScan.maxRetestRounds"), { target: { value: "3" } });
  fireEvent.change(screen.getByPlaceholderText("10"), { target: { value: "20" } });
  fireEvent.click(screen.getByRole("button", { name: /newScan\.startScan/ }));

  await waitFor(() => expect(createScan).toHaveBeenCalled());
  expect(submittedConfig().advanced).toMatchObject({
    retest_arm: "B",
    max_retest_rounds: 3,
    health_window_size: 20,
  });
});

it("turning the retest off again drops the arm from the request", async () => {
  renderPage();
  fireEvent.click(screen.getByText("newScan.advancedModes"));
  fireEvent.click(screen.getByRole("button", { name: "newScan.retestArmB" }));
  fireEvent.click(screen.getByRole("button", { name: "newScan.retestOff" }));
  fireEvent.click(screen.getByRole("button", { name: /newScan\.startScan/ }));

  await waitFor(() => expect(createScan).toHaveBeenCalled());
  const advanced = submittedConfig().advanced;
  expect(advanced?.retest_arm).toBeUndefined();
  expect(advanced?.max_retest_rounds).toBeUndefined();
});

it("the MailBot preset imports its sample adapter and scans through it", async () => {
  renderPage();
  fireEvent.click(screen.getByRole("button", { name: /newScan\.presetMailBot\b/ }));

  await waitFor(() => expect(installSampleAdapter).toHaveBeenCalledWith("mailbot"));
  await waitFor(() => expect(toast).toHaveBeenCalledWith("success", "newScan.presetLoaded"));
  fireEvent.click(screen.getByRole("button", { name: /newScan\.startScan/ }));

  await waitFor(() => expect(createScan).toHaveBeenCalled());
  const config = submittedConfig();
  expect(config.target_type).toBe("adapter");
  expect(config.adapter_id).toBe("adapter-mailbot");
  expect(config.attack_categories).toContain("indirect_injection");
  expect(config.advanced).toMatchObject({ retest_arm: "B", parallel_attacks: 1 });
});

it("the FinanceBot preset uses the backend's mock-target address", async () => {
  renderPage();
  fireEvent.click(screen.getByRole("button", { name: /newScan\.presetFinanceBot\b/ }));

  await waitFor(() => expect(listMockTargets).toHaveBeenCalled());
  await waitFor(() => expect(toast).toHaveBeenCalledWith("success", "newScan.presetLoaded"));
  fireEvent.click(screen.getByRole("button", { name: /newScan\.startScan/ }));

  await waitFor(() => expect(createScan).toHaveBeenCalled());
  const config = submittedConfig();
  expect(config.target_type).toBe("custom");
  expect(config.target_url).toBe("http://financebot:8001/chat");
});
