import { describe, expect, it } from "vitest";
import { en } from "../i18n/en";
import { zh } from "../i18n/zh";
import {
  builtinLevelLabel,
  categoryDescription,
  categoryLabel,
  isInterruptedScan,
  localizeHealthReason,
  INTERRUPT_GRACE_MS,
  owaspItemLabel,
  phaseLabel,
  retestActionLabel,
  riskLevelLabel,
  scanStatusLabel,
  strategyLabel,
  targetTypeLabel,
  type Translate,
} from "./labels";

/** A `t` over one locale table that behaves like useLocale's: key when missing, `{var}` substitution. */
function translator(table: unknown): Translate {
  return (key, vars) => {
    let node: unknown = table;
    for (const part of key.split(".")) {
      if (node == null || typeof node !== "object") return key;
      node = (node as Record<string, unknown>)[part];
    }
    if (typeof node !== "string") return key;
    let text = node;
    for (const [k, v] of Object.entries(vars ?? {})) text = text.replace(`{${k}}`, String(v));
    return text;
  };
}

const tZh = translator(zh);
const tEn = translator(en);

describe("shared labels", () => {
  it("translates every attack category id the templates ship with", () => {
    const ids = [
      "prompt_injection", "system_prompt_extraction", "jailbreak", "information_disclosure",
      "indirect_injection", "excessive_agency", "denial_of_service",
    ];
    for (const id of ids) {
      expect(categoryLabel(tZh, id)).toMatch(/[一-鿿]/);
      expect(categoryDescription(tZh, id)).toMatch(/[一-鿿]/);
    }
    expect(categoryLabel(tZh, "indirect_injection")).toBe("间接提示注入");
    expect(categoryLabel(tEn, "indirect_injection")).toBe("Indirect Prompt Injection");
  });

  it("falls back to the server name, then the spaced id, for unknown categories", () => {
    expect(categoryLabel(tZh, "custom_category", "Custom Category")).toBe("Custom Category");
    expect(categoryLabel(tZh, "custom_category")).toBe("custom category");
    expect(categoryDescription(tZh, "custom_category", "server text")).toBe("server text");
  });

  it("maps statuses, target types, risk levels and internal action ids", () => {
    expect(scanStatusLabel(tZh, "pending")).toBe("等待中");
    expect(scanStatusLabel(tZh, "interrupted")).toBe("已中断");
    expect(targetTypeLabel(tZh, "claude")).toBe("Claude");
    expect(targetTypeLabel(tZh, "builtin_vulnerable")).toBe("内置靶场");
    expect(targetTypeLabel(tZh, "openai_compatible")).toBe("OpenAI 兼容");
    expect(riskLevelLabel(tZh, "critical")).toBe("严重");
    expect(riskLevelLabel(tZh, "none")).toBe("无风险");
    expect(retestActionLabel(tZh, "run_canary_retest")).toBe("Canary 重测");
    expect(phaseLabel(tZh, "quartet_controls")).toBe("四元对照");
    expect(strategyLabel(tZh, "mutation")).toBe("编码变换");
    expect(owaspItemLabel(tZh, "LLM07")).toBe("系统提示词泄露");
    expect(builtinLevelLabel(tZh, 1)).toEqual({ name: "等级 1 · 无防护", desc: "未做任何安全防护" });
  });

  it("keeps the English UI in English", () => {
    expect(scanStatusLabel(tEn, "cancelled")).toBe("Cancelled");
    expect(riskLevelLabel(tEn, "high")).toBe("High");
    expect(builtinLevelLabel(tEn, 4).name).toBe("Level 4 - Strong Defense");
  });
});

describe("isInterruptedScan", () => {
  const created = "2026-10-25T00:00:00Z";
  const later = new Date(created).getTime() + INTERRUPT_GRACE_MS + 1;

  it("flags a pending or running scan that no runner is executing", () => {
    expect(isInterruptedScan({ status: "pending", created_at: created, runner_active: false }, later)).toBe(true);
    expect(isInterruptedScan({ status: "running", created_at: created, runner_active: false }, later)).toBe(true);
  });

  it("gives a just-created scan time to reach its runner", () => {
    expect(isInterruptedScan({ status: "pending", created_at: created, runner_active: false }, later - 2)).toBe(false);
  });

  it("ignores live, finished, and unknown-liveness scans", () => {
    expect(isInterruptedScan({ status: "running", created_at: created, runner_active: true }, later)).toBe(false);
    expect(isInterruptedScan({ status: "completed", created_at: created, runner_active: false }, later)).toBe(false);
    expect(isInterruptedScan({ status: "pending", created_at: created }, later)).toBe(false);
  });
});

describe("localizeHealthReason", () => {
  it("translates the runtime health templates with their numbers", () => {
    expect(localizeHealthReason(tZh, "High non-evaluable ratio during scan: 8/10 recent responses."))
      .toBe("扫描中不可评估响应占比偏高：最近 8/10 条。");
    expect(localizeHealthReason(tZh, "Target emitted 20 consecutive non-evaluable responses (http_502); dead-man switch tripped."))
      .toBe("目标连续 20 次返回不可评估的响应（http_502），已触发熔断。");
    expect(localizeHealthReason(tZh, "Repeated non-evaluable signature during scan: transport_error (5 consecutive responses)."))
      .toBe("扫描中同一不可评估特征重复出现：transport_error（连续 5 次）。");
  });

  it("translates the probe templates together with their detail sentence", () => {
    expect(localizeHealthReason(tZh,
      "Health probe detected repeated non-evaluable benign responses. The request failed before a stable model response could be evaluated. Matched signature: transport_error."))
      .toBe("健康探测：良性请求连续返回不可评估的响应。请求在得到稳定的模型响应之前就已失败。 匹配特征：transport_error。");
    expect(localizeHealthReason(tZh,
      "Health probe detected 1/2 non-evaluable benign responses. The endpoint returned an empty response, so there is no model output to evaluate."))
      .toBe("健康探测：1/2 个良性请求返回不可评估的响应。接口返回空响应，没有可评估的模型输出。");
  });

  it("passes unknown text through and keeps English in the English UI", () => {
    expect(localizeHealthReason(tZh, "upstream said no")).toBe("upstream said no");
    expect(localizeHealthReason(tZh, null)).toBeNull();
    const english = "High non-evaluable ratio during scan: 8/10 recent responses.";
    expect(localizeHealthReason(tEn, english)).toBe(english);
  });
});
