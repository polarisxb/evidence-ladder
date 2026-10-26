import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LocaleProvider, useLocale } from "../i18n";
import type { ResponseEvaluation } from "../types";
import { ResponseEvaluationPanel } from "./ResponseEvaluationPanel";

const MODEL_REPLY: ResponseEvaluation = {
  response_origin: "model", origin_confidence: "high", evaluation_validity: "evaluable",
};
const TRANSPORT_FAILURE: ResponseEvaluation = {
  response_origin: "transport_error", origin_confidence: "medium", evaluation_validity: "not_evaluable",
  invalid_reason: "transport_error", http_status: 502,
};

function Panel(props: { evaluation: ResponseEvaluation; variant?: "card" | "inline" }) {
  const { t } = useLocale();
  return <ResponseEvaluationPanel {...props} t={t} />;
}

const renderZh = (props: { evaluation: ResponseEvaluation; variant?: "card" | "inline" }) =>
  render(<LocaleProvider><Panel {...props} /></LocaleProvider>);

describe("ResponseEvaluationPanel", () => {
  it("renders as a single line inside another section, without the boxed card or emoji", () => {
    const { container } = renderZh({ evaluation: MODEL_REPLY, variant: "inline" });

    expect(screen.getByText("响应来源")).toBeInTheDocument();
    expect(screen.getByText("攻击请求已到达模型层")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/🧠|✅/);
    expect(container.querySelector(".rounded-lg.border")).toBeNull();
  });

  it("shows the confidence and detail values in Chinese, not raw tokens", () => {
    renderZh({ evaluation: TRANSPORT_FAILURE, variant: "inline" });

    expect(screen.getByText("中置信度")).toBeInTheDocument();
    expect(screen.queryByText("Medium")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { expanded: false }));
    expect(screen.getAllByText("传输失败")).toHaveLength(2); // origin + invalid reason
    expect(screen.queryByText("Transport Error")).not.toBeInTheDocument();
    expect(screen.getByText("502")).toBeInTheDocument();
  });

  it("keeps the card form for pages that show it on its own", () => {
    const { container } = renderZh({ evaluation: MODEL_REPLY });

    expect(container.querySelector(".rounded-lg.border")).not.toBeNull();
    expect(screen.getByText("高置信度")).toBeInTheDocument();
    expect(screen.queryByText("High")).not.toBeInTheDocument();
  });
});
