import { describe, it, expect } from "vitest";
import { formatDate, formatDuration, truncate } from "./format";

describe("formatDate", () => {
  it("returns a placeholder for null", () => {
    expect(formatDate(null)).toBe("-");
  });

  it("formats an ISO timestamp into a non-empty string", () => {
    expect(formatDate("2026-01-02T03:04:05Z")).not.toBe("-");
  });
});

describe("formatDuration", () => {
  it("returns a placeholder when either bound is missing", () => {
    expect(formatDuration(null, "2026-01-01T00:00:10Z")).toBe("-");
    expect(formatDuration("2026-01-01T00:00:00Z", null)).toBe("-");
  });

  it("formats sub-minute durations as seconds", () => {
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:00:42Z")).toBe("42s");
  });

  it("formats durations over a minute as minutes and seconds", () => {
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:01:05Z")).toBe("1m 5s");
  });
});

describe("truncate", () => {
  it("leaves short strings untouched", () => {
    expect(truncate("hello", 100)).toBe("hello");
  });

  it("truncates and appends an ellipsis when over the limit", () => {
    expect(truncate("abcdef", 3)).toBe("abc...");
  });

  it("treats the limit as inclusive", () => {
    expect(truncate("abc", 3)).toBe("abc");
  });
});
