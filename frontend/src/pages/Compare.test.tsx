import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { listScans } from "../api/scans";
import { compareScans, type CompareResult } from "../api/stats";
import { LocaleProvider, useLocale } from "../i18n";
import { Compare } from "./Compare";

vi.mock("../api/scans", () => ({ listScans: vi.fn() }));
vi.mock("../api/stats", () => ({ compareScans: vi.fn() }));
vi.mock("../components/Toast", () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock("../i18n", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../i18n")>();
  return { ...actual, useLocale: vi.fn(actual.useLocale) };
});

describe("Compare vulnerability lists", () => {
  it("does not invent a score delta when a scan cannot be scored", async () => {
    vi.mocked(listScans).mockResolvedValue({ data: [{ id: "a", name: "A" }, { id: "b", name: "B" }] } as Awaited<ReturnType<typeof listScans>>);
    vi.mocked(compareScans).mockResolvedValue({
      scan_a: { name: "A", overall_score: null, categories: {} },
      scan_b: { name: "B", overall_score: 100, categories: {} },
      score_diff: null, fixed_vulnerabilities: [], new_vulnerabilities: [], persistent_vulnerabilities: [],
    } as unknown as CompareResult);
    render(<Compare />);
    await screen.findAllByRole("option", { name: "compare.scanOption" });
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "a" } });
    fireEvent.change(selects[1], { target: { value: "b" } });
    fireEvent.click(screen.getByRole("button", { name: "compare.compareScans" }));
    expect(await screen.findByText("compare.scoreUnavailable")).toBeInTheDocument();
    expect(screen.queryByText("+100")).not.toBeInTheDocument();
  });
  it("keeps locale hooks stable across empty, populated, and empty results", async () => {
    vi.mocked(listScans).mockResolvedValue({
      data: [{ id: "a", name: "A" }, { id: "b", name: "B" }],
    } as Awaited<ReturnType<typeof listScans>>);
    render(<Compare />);
    await screen.findAllByRole("option", { name: "compare.scanOption" });
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "a" } });
    fireEvent.change(selects[1], { target: { value: "b" } });

    const hookCounts: number[] = [];
    for (const items of [[], ["fixture finding"], []]) {
      let resolve!: (result: CompareResult) => void;
      vi.mocked(compareScans).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
      fireEvent.click(screen.getByRole("button", { name: "compare.compareScans" }));
      await screen.findByRole("button", { name: "compare.comparing" });
      vi.mocked(useLocale).mockClear();
      await act(async () => {
        resolve({
          scan_a: { name: "A", overall_score: 50, categories: {} },
          scan_b: { name: "B", overall_score: 50, categories: {} },
          score_diff: 0,
          fixed_vulnerabilities: items,
          new_vulnerabilities: items,
          persistent_vulnerabilities: items,
        } as CompareResult);
      });
      expect(screen.getAllByText(items.length ? "fixture finding" : "common.none")).toHaveLength(3);
      // useContext alone does not always trigger React's hook-order warning;
      // also count the real hook calls so conditional useLocale cannot regress.
      hookCounts.push(vi.mocked(useLocale).mock.calls.length);
    }
    expect(hookCounts).toEqual([6, 6, 6]);
  });
});

it("labels scan options with a Chinese score and names unnamed scans", async () => {
  vi.mocked(listScans).mockResolvedValue({
    data: [
      { id: "a", name: "A", overall_score: 87.5, created_at: "2026-10-01T08:00:00Z" },
      { id: "b", name: "", overall_score: null, created_at: "2026-10-02T08:00:00Z" },
    ],
  } as Awaited<ReturnType<typeof listScans>>);
  render(<LocaleProvider><Compare /></LocaleProvider>);

  expect((await screen.findAllByRole("option", { name: "A（评分：87.5）" })).length).toBe(2);
  expect(screen.getAllByRole("option", { name: /^未命名扫描 · .*（评分：无法评分）$/ })).toHaveLength(2);
  expect(screen.queryByRole("option", { name: /Posture/ })).not.toBeInTheDocument();
});
