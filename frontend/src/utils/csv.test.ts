import { describe, it, expect } from "vitest";
import { buildCsvString } from "./csv";

describe("buildCsvString", () => {
  it("emits a header line followed by rows joined with CRLF", () => {
    const csv = buildCsvString(["a", "b"], [{ a: "1", b: "2" }]);
    expect(csv).toBe("a,b\r\n1,2");
  });

  it("orders cells by the header list and blanks missing keys", () => {
    const csv = buildCsvString(["a", "b", "c"], [{ b: "2", a: "1" }]);
    expect(csv).toBe("a,b,c\r\n1,2,");
  });

  it("quotes cells containing commas, quotes or newlines and doubles inner quotes", () => {
    const csv = buildCsvString(["v"], [
      { v: "a,b" },
      { v: 'say "hi"' },
      { v: "line1\nline2" },
    ]);
    expect(csv).toBe('v\r\n"a,b"\r\n"say ""hi"""\r\n"line1\nline2"');
  });

  it("renders null and undefined as empty cells", () => {
    const csv = buildCsvString(["a", "b"], [{ a: null, b: undefined }]);
    expect(csv).toBe("a,b\r\n,");
  });
});
