import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { APP_VERSION, APP_VERSION_LABEL, versionLabel } from "../../appInfo";
import { LocaleProvider } from "../../i18n";
import { zh } from "../../i18n/zh";
import { Sidebar } from "./Sidebar";

describe("app identity", () => {
  it("formats the version the way the registration documents do", () => {
    expect(versionLabel("1.0.0")).toBe("V1.0");
    expect(versionLabel("2.3.4")).toBe("V2.3");
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
  });

  it("shows the registered software name and version in the sidebar", () => {
    render(<LocaleProvider><MemoryRouter><Sidebar /></MemoryRouter></LocaleProvider>);

    expect(screen.getByText(zh.app.fullName)).toBeInTheDocument();
    expect(screen.getByText(`${APP_VERSION_LABEL} · E0–E5`)).toBeInTheDocument();
  });
});
