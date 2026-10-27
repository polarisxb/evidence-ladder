import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { getScan } from "../api/scans";
import { useWebSocket } from "../hooks/useWebSocket";
import type { ScanTask } from "../types";
import { ScanProgress } from "./ScanProgress";

const { toast } = vi.hoisted(() => ({ toast: vi.fn() }));
vi.mock("../api/scans", () => ({ getScan: vi.fn(), cancelScan: vi.fn(), finalizeStuckScan: vi.fn() }));
vi.mock("../api/reports", () => ({ getAttackResults: vi.fn().mockResolvedValue([]) }));
vi.mock("../components/Toast", () => ({ useToast: () => ({ toast }) }));
vi.mock("../hooks/useWebSocket", () => ({ useWebSocket: vi.fn() }));

it("does not fall back to a stale score after an unscorable completion event", async () => {
  vi.mocked(getScan).mockResolvedValue({
    id: "fixture", status: "completed", total_attacks: 1, completed_attacks: 1,
    overall_score: 100, target_type: "custom", target_url: "https://fixture.example.com",
  } as ScanTask);
  vi.mocked(useWebSocket).mockReturnValue({ connected: true, events: [{ type: "scan_completed", overall_score: null }] });
  render(<MemoryRouter initialEntries={["/scan/fixture"]}>
    <Routes><Route path="/scan/:taskId" element={<ScanProgress />} /></Routes>
  </MemoryRouter>);
  await screen.findByText("https://fixture.example.com");
  expect(screen.getByRole("button", { name: /^scanProgress.viewReport/ })).not.toHaveTextContent("100");
});

it("shows cancellation immediately even while the API still returns running", async () => {
  vi.mocked(getScan).mockResolvedValue({
    id: "fixture", status: "running", total_attacks: 4, completed_attacks: 1,
    target_type: "custom", target_url: "https://fixture.example.com",
  } as ScanTask);
  vi.mocked(useWebSocket).mockReturnValue({ connected: true, events: [] });
  const page = (
    <MemoryRouter initialEntries={["/scan/fixture"]}>
      <Routes><Route path="/scan/:taskId" element={<ScanProgress />} /></Routes>
    </MemoryRouter>
  );
  const { rerender } = render(page);
  await screen.findByText("https://fixture.example.com");
  expect(screen.getByText("scanProgress.scanning")).toBeInTheDocument();
  vi.mocked(useWebSocket).mockReturnValue({
    connected: true, events: [{ type: "scan_cancelled", completed: 2, total: 4 }],
  });
  rerender(
    <MemoryRouter initialEntries={["/scan/fixture"]}>
      <Routes><Route path="/scan/:taskId" element={<ScanProgress />} /></Routes>
    </MemoryRouter>,
  );
  expect(screen.queryByText("scanProgress.scanning")).not.toBeInTheDocument();
  expect(screen.getByText("scanProgress.scanEndedEarly")).toBeInTheDocument();
  expect(screen.getByText("2/4 scanProgress.cases")).toBeInTheDocument();
});

it("tells the user a pending scan with no runner has been interrupted", async () => {
  vi.mocked(getScan).mockResolvedValue({
    id: "fixture", status: "pending", total_attacks: 0, completed_attacks: 0, runner_active: false,
    created_at: "2026-01-01T00:00:00Z", target_type: "builtin_vulnerable", target_url: "https://orphan.example.com",
  } as ScanTask);
  vi.mocked(useWebSocket).mockReturnValue({ connected: false, events: [] });
  render(<MemoryRouter initialEntries={["/scan/fixture"]}>
    <Routes><Route path="/scan/:taskId" element={<ScanProgress />} /></Routes>
  </MemoryRouter>);

  await screen.findByText("https://orphan.example.com");
  expect(screen.getByText("scanProgress.interrupted")).toBeInTheDocument();
  expect(screen.getByText("scanProgress.interruptedHint")).toBeInTheDocument();
  expect(screen.queryByText("scanProgress.scanning")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "scanProgress.cancelScan" })).toBeInTheDocument();
});
