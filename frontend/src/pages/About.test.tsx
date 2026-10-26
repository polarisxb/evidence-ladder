import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { LocaleProvider } from "../i18n";
import { About } from "./About";

it("renders the subtitle emphasis as bold text, not literal asterisks", () => {
  render(<LocaleProvider><About /></LocaleProvider>);

  expect(document.body.textContent).not.toContain("**");
  expect(screen.getByText("审视").tagName).toBe("STRONG");
  expect(screen.getByText("E0–E5").tagName).toBe("STRONG");
});

it("describes the framework coverage in Chinese", () => {
  render(<LocaleProvider><About /></LocaleProvider>);

  expect(screen.getByText("66 项攻击技术")).toBeInTheDocument();
  expect(screen.getByText("0–10 分制")).toBeInTheDocument();
  expect(screen.queryByText("66 techniques")).not.toBeInTheDocument();
});
