import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { LocaleProvider } from "../i18n";
import type { ModelProvider } from "../types";
import { Settings } from "./Settings";

vi.mock("../components/Toast", () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock("../api/client", () => ({
  request: vi.fn().mockResolvedValue({
    data: {
      openai_api_key_set: true, openai_base_url: "https://api.example.com", openai_model: "model-a",
      openai_mini_model: "model-b", database_url: "sqlite:///fixture.db", debug: false,
    },
  }),
}));
vi.mock("../api/modelProviders", () => ({
  listModelProviders: vi.fn().mockResolvedValue([{
    id: "p1", name: "Fixture provider", provider_type: "deepseek", api_key_set: true, api_key_count: 2,
    api_keys: [], base_url: "https://api.example.com", judge_model: null, mini_model: null,
    is_judge_default: true, is_generation_default: true, enabled: true,
    created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
  } satisfies ModelProvider]),
  createModelProvider: vi.fn(),
  deleteModelProvider: vi.fn(),
  fetchProviderModels: vi.fn().mockResolvedValue([]),
  testModelProvider: vi.fn(),
  updateModelProvider: vi.fn(),
}));

it("labels the API endpoint and the key count", async () => {
  render(<LocaleProvider><Settings /></LocaleProvider>);

  expect(await screen.findByText("2 个密钥")).toBeInTheDocument();
  expect(screen.getByText(/^API 地址:/)).toBeInTheDocument();
  expect(screen.queryByText(/\bkeys?\b/)).not.toBeInTheDocument();
});
