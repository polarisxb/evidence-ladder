/**
 * Lightweight CSV generation utilities — no dependencies needed.
 */

/** Escape a single value for CSV: wrap in quotes if it contains comma, newline or quote. */
function escapeCell(value: unknown): string {
  if (value == null) return "";
  const str = String(value);
  if (str.includes(",") || str.includes("\n") || str.includes('"')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Build a CSV string from an array of header names and an array of row objects.
 * Rows are ordered by `headers`; missing keys produce an empty cell.
 */
export function buildCsvString(
  headers: string[],
  rows: Record<string, unknown>[],
): string {
  const headerLine = headers.map(escapeCell).join(",");
  const dataLines = rows.map((row) =>
    headers.map((h) => escapeCell(row[h])).join(","),
  );
  return [headerLine, ...dataLines].join("\r\n");
}

/**
 * Trigger a browser download of the given CSV content.
 */
export function downloadCsv(filename: string, csvContent: string): void {
  const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
