import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { request } from "../api/client";
import { LocaleProvider } from "../i18n";
import { Templates } from "./Templates";

vi.mock("../components/Toast", () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock("../api/client", () => ({ request: vi.fn() }));

it("names attack categories by taxonomy name with a Chinese description, keeping unknown ones as sent", async () => {
  vi.mocked(request).mockResolvedValue({
    data: [
      {
        category: "indirect_injection", category_name: "Indirect Prompt Injection", owasp_id: "LLM01",
        description: "Test whether the target AI can be manipulated via malicious instructions.", template_count: 6,
      },
      {
        category: "custom_pack", category_name: "Custom Pack", owasp_id: "LLM10",
        description: "Team-specific templates.", template_count: 2,
      },
    ],
  });
  render(<LocaleProvider><Templates /></LocaleProvider>);

  expect(await screen.findByText("Indirect Prompt Injection")).toBeInTheDocument();
  expect(screen.getByText(/测试目标能否被外部内容/)).toBeInTheDocument();
  expect(screen.queryByText(/Test whether the target AI can be manipulated via malicious/)).not.toBeInTheDocument();
  expect(screen.getByText("Custom Pack")).toBeInTheDocument();
  expect(screen.getByText("Team-specific templates.")).toBeInTheDocument();
});
