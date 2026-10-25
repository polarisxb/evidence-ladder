import { describe, expect, it, vi } from "vitest";
import type { Adapter, MockTarget, ScanConfig } from "../types";
import { resolveDemoPreset } from "./demoPresets";

const BASE_CONFIG: ScanConfig = {
  name: "preset fixture",
  target_type: "custom",
  target_url: "",
  target_config: { model: "fallback-model", system_prompt: "You are a bot." },
  attack_categories: ["jailbreak"],
};

const MOCK_TARGETS: MockTarget[] = [
  { key: "financebot", base_url: "http://financebot:8001", chat_url: "http://financebot:8001/chat", sample_adapter: null },
  { key: "mailbot", base_url: "http://localhost:8003", chat_url: "http://localhost:8003/chat", sample_adapter: "mailbot" },
];

const SAMPLE_ADAPTER = { id: "adapter-mailbot", name: "mailbot-agent", enabled: true } as Adapter;

function deps(overrides: Partial<Parameters<typeof resolveDemoPreset>[1]> = {}) {
  return {
    installSampleAdapter: vi.fn().mockResolvedValue({ adapter: SAMPLE_ADAPTER, created: true }),
    listMockTargets: vi.fn().mockResolvedValue(MOCK_TARGETS),
    platformModel: "deepseek-v4-flash",
    ...overrides,
  };
}

describe("resolveDemoPreset", () => {
  it("scans an agent target through its imported sample adapter", async () => {
    const d = deps();
    const { config, adapter } = await resolveDemoPreset({ config: BASE_CONFIG, sampleAdapter: "mailbot" }, d);

    expect(d.installSampleAdapter).toHaveBeenCalledWith("mailbot");
    expect(adapter).toBe(SAMPLE_ADAPTER);
    expect(config).toMatchObject({ target_type: "adapter", adapter_id: "adapter-mailbot", target_url: "" });
    expect(config.target_config).toBeUndefined();
  });

  it("points a text-only target at the backend's configured mock address", async () => {
    const d = deps();
    const { config } = await resolveDemoPreset({ config: BASE_CONFIG, mockTarget: "financebot" }, d);

    expect(config.target_type).toBe("custom");
    expect(config.target_url).toBe("http://financebot:8001/chat");
    expect(d.installSampleAdapter).not.toHaveBeenCalled();
  });

  it("fails loudly when the backend does not know the mock target", async () => {
    await expect(
      resolveDemoPreset({ config: BASE_CONFIG, mockTarget: "financebot" }, deps({
        listMockTargets: vi.fn().mockResolvedValue([]),
      })),
    ).rejects.toThrow("Unknown mock target: financebot");
  });

  it("uses the platform model for model presets and keeps the rest of the target config", async () => {
    const { config } = await resolveDemoPreset({ config: BASE_CONFIG, usePlatformModel: true }, deps());

    expect(config.target_config).toEqual({ model: "deepseek-v4-flash", system_prompt: "You are a bot." });
  });

  it("keeps the preset model when the platform model is unknown", async () => {
    const { config } = await resolveDemoPreset(
      { config: BASE_CONFIG, usePlatformModel: true },
      deps({ platformModel: null }),
    );

    expect(config.target_config?.model).toBe("fallback-model");
  });
});
