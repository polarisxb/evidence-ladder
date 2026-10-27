import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { APP_VERSION_LABEL } from "../appInfo";
import { LocaleProvider } from "../i18n";
import { About } from "./About";

const renderAbout = () => render(<LocaleProvider><About /></LocaleProvider>);

describe("About page", () => {
  it("leads with the registered name, version and positioning", () => {
    renderAbout();

    expect(screen.getByRole("heading", { level: 1, name: "大模型应用多源证据分层安全评测平台" })).toBeInTheDocument();
    expect(screen.getByText(APP_VERSION_LABEL)).toBeInTheDocument();
    expect(screen.getByText(/Judge 只是其中一层证据，不是唯一裁判/)).toBeInTheDocument();
    expect(screen.getByText("E0–E5")).toBeInTheDocument();
  });

  it("shows the evidence ladder from strongest to weakest, method names in English", () => {
    renderAbout();

    const ladder = screen.getByRole("list", { name: "证据阶梯" });
    const rungs = within(ladder).getAllByRole("listitem");
    expect(rungs.map((rung) => rung.textContent?.slice(0, 2))).toEqual(["E5", "E4", "E3", "E2", "E1", "E0"]);
    expect(within(rungs[0]).getByText("Probe-Verified")).toBeInTheDocument();
    expect(within(rungs[0]).getByText("业务状态差异或探针查询确认")).toBeInTheDocument();
    expect(within(rungs[5]).getByText("Not Evaluable")).toBeInTheDocument();
  });

  it("explains the quartet, conflict-driven retest and judge calibration", () => {
    renderAbout();

    for (const variant of ["Clean", "Attack", "Quoted Attack", "Benign Distractor"]) {
      expect(screen.getByText(variant)).toBeInTheDocument();
    }
    expect(screen.getByText("裁判判成功，但规则与探针都没有证据")).toBeInTheDocument();
    expect(screen.getByText("业务探针验证")).toBeInTheDocument();
    expect(screen.getByText("精确率 · 召回率 · 误报率 · 人工复核覆盖率")).toBeInTheDocument();
  });

  it("describes the platform without stale or decorative leftovers", () => {
    const { container } = renderAbout();

    expect(screen.getByText("AutoTest 自动测试")).toBeInTheDocument();
    expect(screen.getByText("MailBot · ShopBot · FinanceBot")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/GPT-4o|\*\*|🖥️|🧠/);
  });

  it("lists standards and opens papers in a new tab safely", () => {
    renderAbout();

    expect(screen.getByText("66 项攻击技术")).toBeInTheDocument();
    expect(screen.getByText("0–10 分制")).toBeInTheDocument();
    const paper = screen.getByRole("link", { name: /A Coin Flip for Safety/ });
    expect(paper).toHaveAttribute("href", "https://arxiv.org/abs/2603.06594");
    expect(paper).toHaveAttribute("target", "_blank");
    expect(paper).toHaveAttribute("rel", "noopener noreferrer");
  });
});
