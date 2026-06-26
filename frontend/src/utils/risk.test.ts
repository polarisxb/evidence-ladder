import { describe, it, expect } from "vitest";
import { scoreToRisk, riskLabel } from "./risk";

describe("scoreToRisk", () => {
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
  it("returns the upper-cased label for each level", () => {
    expect(riskLabel("critical")).toBe("CRITICAL");
    expect(riskLabel("high")).toBe("HIGH");
    expect(riskLabel("medium")).toBe("MEDIUM");
    expect(riskLabel("low")).toBe("LOW");
    expect(riskLabel("none")).toBe("SAFE");
  });
});
