import { cloneElement, type ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCategorySuccessRate, getRiskDistribution, getScoreTrend } from "../../api/stats";
import { LocaleProvider } from "../../i18n";
import { CategoryBarChart } from "./CategoryBarChart";
import { CategoryRadarChart } from "./CategoryRadarChart";
import { RiskPieChart } from "./RiskPieChart";
import { ScoreTrendChart } from "./ScoreTrendChart";

vi.mock("../../api/stats", () => ({
  getCategorySuccessRate: vi.fn(),
  getRiskDistribution: vi.fn(),
  getScoreTrend: vi.fn(),
}));

// jsdom has no layout, so give charts a fixed size to make them draw.
vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactElement }) =>
      cloneElement(children as ReactElement<{ width: number; height: number }>, { width: 800, height: 300 }),
  };
});

const zh = (ui: ReactElement) => render(<LocaleProvider>{ui}</LocaleProvider>);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("dashboard charts in the Chinese UI", () => {
  it("labels every attack category by its taxonomy name, including ones the old map missed", async () => {
    vi.mocked(getCategorySuccessRate).mockResolvedValue([
      { category: "information_disclosure", total: 4, successful: 1, evaluable: 4, not_evaluable: 0, rate: 25 },
      { category: "indirect_injection", total: 4, successful: 0, evaluable: 4, not_evaluable: 0, rate: 0 },
      { category: "excessive_agency", total: 4, successful: 2, evaluable: 4, not_evaluable: 0, rate: 50 },
    ]);
    zh(<CategoryBarChart />);

    // Recharts also renders a hidden copy of tick text for measuring.
    expect((await screen.findAllByText("Information Disclosure")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Indirect Prompt Injection").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Excessive Agency").length).toBeGreaterThan(0);
    expect(screen.queryByText("indirect_injection")).not.toBeInTheDocument();
    expect(screen.getAllByText("成功率 %").length).toBeGreaterThan(0);
  });

  it("names risk levels in Chinese in the pie legend", async () => {
    vi.mocked(getRiskDistribution).mockResolvedValue({ critical: 2, high: 1, medium: 0, low: 0 });
    zh(<RiskPieChart />);

    expect(await screen.findByText("严重")).toBeInTheDocument();
    expect(screen.getByText("高危")).toBeInTheDocument();
    expect(screen.queryByText("Critical")).not.toBeInTheDocument();
  });

  it("marks the trend chart bands with Chinese risk labels", async () => {
    vi.mocked(getScoreTrend).mockResolvedValue([
      { scan_id: "a", name: "scan-a", score: 80, date: "2026-10-01" },
      { scan_id: "b", name: "scan-b", score: 40, date: "2026-10-02" },
    ]);
    zh(<ScoreTrendChart />);

    expect(await screen.findByText("低危")).toBeInTheDocument();
    expect(screen.getByText("中危")).toBeInTheDocument();
    expect(screen.queryByText("MED")).not.toBeInTheDocument();
  });

  it("shows empty states in Chinese", async () => {
    vi.mocked(getCategorySuccessRate).mockResolvedValue([]);
    vi.mocked(getRiskDistribution).mockResolvedValue({ critical: 0, high: 0, medium: 0, low: 0 });
    vi.mocked(getScoreTrend).mockResolvedValue([]);
    zh(<><CategoryBarChart /><RiskPieChart /><ScoreTrendChart /></>);

    expect(await screen.findByText("暂无攻击数据")).toBeInTheDocument();
    expect(await screen.findByText("未发现漏洞")).toBeInTheDocument();
    expect(screen.getByText("暂无扫描数据")).toBeInTheDocument();
  });

  it("asks for two evaluable categories before drawing the radar", () => {
    zh(<CategoryRadarChart scores={[]} />);
    expect(screen.getByText("至少需要 2 个可评估的类别才能绘制雷达图")).toBeInTheDocument();
  });
});
