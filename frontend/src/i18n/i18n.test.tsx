import React from "react";
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { en } from "./en";
import { zh } from "./zh";
import { LocaleProvider, useLocale } from "./index";

function flattenKeys(obj: Record<string, unknown>, prefix = ""): string[] {
  const keys: string[] = [];
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (v !== null && typeof v === "object") {
      keys.push(...flattenKeys(v as Record<string, unknown>, path));
    } else {
      keys.push(path);
    }
  }
  return keys;
}

describe("i18n key parity", () => {
  it("zh and en expose an identical set of translation keys", () => {
    const enKeys = new Set(flattenKeys(en as unknown as Record<string, unknown>));
    const zhKeys = new Set(flattenKeys(zh as unknown as Record<string, unknown>));
    const missingInZh = [...enKeys].filter((k) => !zhKeys.has(k));
    const missingInEn = [...zhKeys].filter((k) => !enKeys.has(k));
    expect({ missingInZh, missingInEn }).toEqual({ missingInZh: [], missingInEn: [] });
  });
});

describe("translation function t", () => {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <LocaleProvider>{children}</LocaleProvider>
  );

  it("resolves a nested key for the default (zh) locale", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(result.current.t("common.save")).toBe(zh.common.save);
  });

  it("returns the key itself when it cannot be resolved", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(result.current.t("does.not.exist")).toBe("does.not.exist");
  });

  it("substitutes interpolation variables", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(result.current.t("newScan.modelsLoaded", { n: 7 })).toBe("已加载 7 个可用模型");
  });

  it("switches locale on demand", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    act(() => result.current.setLocale("en"));
    expect(result.current.t("common.save")).toBe(en.common.save);
    expect(result.current.t("newScan.modelsLoaded", { n: 3 })).toBe("3 models available");
  });
});
