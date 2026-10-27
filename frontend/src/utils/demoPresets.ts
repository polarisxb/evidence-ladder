import type { Adapter, MockTarget, SampleAdapterInstallResult, SampleAdapterKey, ScanConfig } from "../types";

/** Where a New Scan preset gets the parts of its target that depend on the deployment. */
export interface DemoPresetSource {
  config: ScanConfig;
  /** Agent mock target scanned through its sample adapter, so tool logs (E4) and the business probe (E5) are collected. */
  sampleAdapter?: SampleAdapterKey;
  /** Text-only mock target, reached at the address the backend is configured with. */
  mockTarget?: MockTarget["key"];
  /** Model preset: use the platform's configured model instead of a hard-coded one. */
  usePlatformModel?: boolean;
}

export interface DemoPresetDeps {
  installSampleAdapter: (key: SampleAdapterKey) => Promise<SampleAdapterInstallResult>;
  listMockTargets: () => Promise<MockTarget[]>;
  platformModel?: string | null;
}

export interface ResolvedDemoPreset {
  config: ScanConfig;
  /** The sample adapter the preset scans through, when it has one. */
  adapter?: Adapter;
}

export async function resolveDemoPreset(
  preset: DemoPresetSource,
  deps: DemoPresetDeps,
): Promise<ResolvedDemoPreset> {
  const { config } = preset;

  if (preset.sampleAdapter) {
    const { adapter } = await deps.installSampleAdapter(preset.sampleAdapter);
    return {
      config: { ...config, target_type: "adapter", adapter_id: adapter.id, target_url: "", target_config: undefined },
      adapter,
    };
  }

  if (preset.mockTarget) {
    const target = (await deps.listMockTargets()).find((item) => item.key === preset.mockTarget);
    if (!target) {
      throw new Error(`Unknown mock target: ${preset.mockTarget}`);
    }
    return { config: { ...config, target_url: target.chat_url } };
  }

  const platformModel = deps.platformModel?.trim();
  if (preset.usePlatformModel && platformModel) {
    return { config: { ...config, target_config: { ...config.target_config, model: platformModel } } };
  }

  return { config };
}
