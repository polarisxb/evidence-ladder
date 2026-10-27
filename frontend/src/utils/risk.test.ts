import { describe, it, expect } from "vitest";
import { scoreToRisk, riskLabel } from "./risk";

describe("scoreToRisk", () => {
  it("keeps unavailable scores distinct from a real zero", () => {
    expect(scoreToRisk(null)).toBe("unknown");
    expect(scoreToRisk(0)).toBe("critical");
  });
  it("maps high scores to low risk", () => {
    expect(scoreToRisk(100)).toBe("low");
    expect(scoreToRisk(90)).toBe("low");
  });

  it("maps the medium band", () => {
    expect(scoreToRisk(89)).toBe("medium");
    expect(scoreToRisk(70)).toBe("medium");
  });

  it("maps the high band", () => {
    expect(scoreToRisk(69)).toBe("high");
    expect(scoreToRisk(50)).toBe("high");
  });

  it("maps low scores to critical risk", () => {
    expect(scoreToRisk(49)).toBe("critical");
    expect(scoreToRisk(0)).toBe("critical");
  });
});

describe("riskLabel", () => {
  const zhRisk: Record<string, string> = {
    "labels.risk.critical": "严重", "labels.risk.high": "高危", "labels.risk.medium": "中危",
    "labels.risk.low": "低危", "labels.risk.none": "无风险", "labels.risk.unknown": "未知",
  };
  const t = (key: string) => zhRisk[key] ?? key;

  it("returns the localized label for each level", () => {
    expect(riskLabel("critical", t)).toBe("严重");
    expect(riskLabel("high", t)).toBe("高危");
    expect(riskLabel("medium", t)).toBe("中危");
    expect(riskLabel("low", t)).toBe("低危");
    expect(riskLabel("none", t)).toBe("无风险");
    expect(riskLabel("unknown", t)).toBe("未知");
  });
});
