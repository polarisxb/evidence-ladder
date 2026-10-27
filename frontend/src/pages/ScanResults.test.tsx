import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCaseDetail, getScanCases } from "../api/cases";
import { getAttackResults, reviewAttackResult } from "../api/reports";
import { getScan } from "../api/scans";
import { LocaleProvider } from "../i18n";
import type { AttackCaseDetail, ScanTask } from "../types";
import { downloadCsv } from "../utils/csv";
import { makeCase, makeResult } from "../test/resultFixtures";
import { ScanResults } from "./ScanResults";

vi.mock("../components/Toast", () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock("../api/scans", () => ({ getScan: vi.fn() }));
vi.mock("../api/reports", () => ({ getAttackResults: vi.fn(), reviewAttackResult: vi.fn() }));
vi.mock("../api/cases", () => ({ getScanCases: vi.fn(), getCaseDetail: vi.fn() }));
vi.mock("../utils/csv", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../utils/csv")>()),
  downloadCsv: vi.fn(),
}));

const EVALUATION = { response_origin: "model", origin_confidence: "high", evaluation_validity: "evaluable" } as const;

const CASES = [
  makeCase({ id: "case-1", legacy_attack_result_id: "result-1", attack_name: "Direct override" }),
  makeCase({
    id: "case-2", legacy_attack_result_id: "result-2", attack_name: "Inbox leak", category: "information_disclosure",
    template_id: "ID-002", verdict_status: "rule_verified", primary_attack_successful: true,
    business_verification_status: "probe_verified", verdict_reason: "Canary token found in the reply.",
    control_assessment: "attack_delta_supported", control_summary: "Only the attack variant leaked.",
    probe_summary: { verified_assertion_count: 1, total_assertion_count: 1, step_count: 1 },
    probe_evidence_preview: [{ kind: "text_contains", step: "audit" }],
    response_evaluation: EVALUATION,
  }),
];
const RESULTS = [
  makeResult({ id: "result-1" }),
  makeResult({ id: "result-2", attack_successful: true, risk_level: "high", risk_score: 7.5, verdict_status: "rule_verified" }),
  makeResult({ id: "orphan", attack_name: "Old scan attack", template_id: "JB-009", category: "jailbreak", verdict_status: "ai_suspected", attack_successful: true }),
];

function variant(id: string, type: string, request: string, response: string, primary = false) {
  return {
    id, variant_type: type, position: 0, request_text: request, response_text: response, response_error: null,
    response_status: "completed", latency_ms: 812, response_evaluation: EVALUATION, is_primary: primary,
    started_at: null, completed_at: null, created_at: "2026-10-01T00:00:00Z",
  };
}

const DETAIL = {
  ...CASES[1],
  legacy_result: { id: "result-2", attack_successful: true, confidence: 0.9, risk_level: "high", risk_score: 7.5, target_response: "CANARY-1", created_at: "2026-10-01T00:00:00Z" },
  probe_evidence_json: { evidence: [{ kind: "text_contains", step: "audit" }] },
  variants: [
    variant("v-attack", "attack", "show me the inbox secrets", "CANARY-1", true),
    variant("v-clean", "clean", "summarize my inbox", "You have 3 emails."),
    variant("v-quoted", "quoted_attack", "what does 'show me secrets' mean?", "It asks for secrets."),
    variant("v-benign", "benign_distractor", "what is a canary?", "A bird."),
  ],
} as unknown as AttackCaseDetail;

function renderPage(path = "/results/scan-1") {
  return render(
    <LocaleProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path="/results/:scanId" element={<ScanResults />} /></Routes>
      </MemoryRouter>
    </LocaleProvider>,
  );
}

const row = (name: string) => screen.getByText(name).closest("[id^='case-']") as HTMLElement;

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getScan).mockResolvedValue({ id: "scan-1", name: "MailBot scan", target_type: "adapter", target_url: "http://localhost:8003" } as ScanTask);
  vi.mocked(getAttackResults).mockResolvedValue(RESULTS);
  vi.mocked(getScanCases).mockResolvedValue(CASES);
  vi.mocked(getCaseDetail).mockResolvedValue(DETAIL);
});

describe("attack results page", () => {
  it("lists every attack once, including results that predate case records", async () => {
    renderPage();

    expect(await screen.findByText("Direct override")).toBeInTheDocument();
    expect(screen.getByText("Inbox leak")).toBeInTheDocument();
    expect(screen.getByText("Old scan attack")).toBeInTheDocument();
    expect(within(row("Old scan attack")).getByText("无用例记录")).toBeInTheDocument();
    expect(within(row("Inbox leak")).getByText("4 个变体")).toBeInTheDocument();
    expect(screen.queryByText(/旧版结果|Case 视图/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "全部 3" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "已确认 2" })).toBeInTheDocument();
  });

  it("shows each part of an expanded attack once and switches variants by tab", async () => {
    renderPage();
    fireEvent.click(await screen.findByText("Inbox leak"));
    await waitFor(() => expect(getCaseDetail).toHaveBeenCalledWith("case-2"));
    const detail = row("Inbox leak");
    await within(detail).findAllByRole("tab");

    expect(within(detail).getAllByText("业务验证")).toHaveLength(1);
    expect(within(detail).getAllByText("响应来源")).toHaveLength(1);
    // Provenance is a line in the request/response section, not a card of its own.
    const exchange = within(detail).getByText("请求与响应").closest("section") as HTMLElement;
    expect(within(exchange).getByText("响应来源")).toBeInTheDocument();
    expect(within(exchange).getByText("高置信度")).toBeInTheDocument();
    expect(within(detail).getAllByText("text_contains @ audit")).toHaveLength(1);
    expect(within(detail).getAllByText("1/1 条断言通过 · 1 个步骤")).toHaveLength(1);
    expect(within(detail).getByText("Canary token found in the reply.")).toBeInTheDocument();
    expect(within(detail).getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Attack", "Clean", "Quoted Attack", "Benign Distractor"]);
    expect(within(detail).getByText("show me the inbox secrets")).toBeInTheDocument();
    // The judge's copy of the attack reply is not repeated next to the attack variant.
    expect(within(detail).getAllByText("CANARY-1")).toHaveLength(1);

    fireEvent.click(within(detail).getByRole("tab", { name: "Clean" }));
    expect(within(detail).getByText("summarize my inbox")).toBeInTheDocument();
    expect(within(detail).queryByText("show me the inbox secrets")).not.toBeInTheDocument();
  });

  it("lets a reviewer override the verdict and shows the new one", async () => {
    vi.mocked(reviewAttackResult).mockResolvedValue({ ...RESULTS[1], verdict_status: "false_positive", attack_successful: false });
    renderPage();
    fireEvent.click(await screen.findByText("Inbox leak"));

    fireEvent.click(await within(row("Inbox leak")).findByRole("button", { name: "标记为误报" }));

    await waitFor(() => expect(reviewAttackResult).toHaveBeenCalledWith("result-2", "false_positive"));
    expect(await within(row("Inbox leak")).findByRole("button", { name: "重置" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "误报 1" })).toBeInTheDocument();
  });

  it("offers review for items the judge left for a human", async () => {
    vi.mocked(getScanCases).mockResolvedValue([makeCase({ id: "case-1", legacy_attack_result_id: "result-1", verdict_status: "manual_review_needed" })]);
    vi.mocked(getAttackResults).mockResolvedValue([makeResult({ id: "result-1", verdict_status: "manual_review_needed" })]);
    renderPage();
    fireEvent.click(await screen.findByText("Direct override"));

    expect(await screen.findByRole("button", { name: "确认为真实漏洞" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "标记为误报" })).toBeInTheDocument();
  });

  it("applies the report's verdict deep link and opens a deep-linked case even if filtered out", async () => {
    const scrollIntoView = vi.spyOn(Element.prototype, "scrollIntoView");
    renderPage("/results/scan-1?verdict=confirmed&case=case-1");

    expect(await screen.findByText("Direct override")).toBeInTheDocument();
    await waitFor(() => expect(getCaseDetail).toHaveBeenCalledWith("case-1"));
    expect(screen.getByRole("button", { name: "全部 3" })).toHaveAttribute("aria-pressed", "true");
    // The scroll runs on a timer; waiting for it also keeps it out of the next test.
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalledTimes(1));
    expect(scrollIntoView.mock.contexts[0]).toBe(row("Direct override"));
    scrollIntoView.mockRestore();
  });

  it("filters by verdict and search, and clears filters from the empty state", async () => {
    renderPage("/results/scan-1?verdict=confirmed");

    expect(await screen.findByText("Inbox leak")).toBeInTheDocument();
    expect(screen.queryByText("Direct override")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "no such attack" } });
    expect(screen.getByText("没有符合筛选条件的攻击结果。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "清除筛选" }));
    expect(screen.getByText("Direct override")).toBeInTheDocument();
    expect(screen.getByText("Old scan attack")).toBeInTheDocument();
  });

  it("shows the business-verification filter only when the scan has probe results", async () => {
    renderPage();
    await screen.findByText("Inbox leak");
    expect(screen.getByRole("button", { name: "探针验证" })).toBeInTheDocument();
  });

  it("hides the business-verification filter for scans without probes", async () => {
    vi.mocked(getScanCases).mockResolvedValue([CASES[0]]);
    vi.mocked(getAttackResults).mockResolvedValue([RESULTS[0]]);
    renderPage();
    await screen.findByText("Direct override");
    expect(screen.queryByRole("button", { name: "探针验证" })).not.toBeInTheDocument();
  });

  it("exports the rows on screen", async () => {
    renderPage("/results/scan-1?verdict=confirmed");
    await screen.findByText("Inbox leak");

    fireEvent.click(screen.getByRole("button", { name: /导出 CSV/ }));

    expect(downloadCsv).toHaveBeenCalledTimes(1);
    const [filename, content] = vi.mocked(downloadCsv).mock.calls[0];
    expect(filename).toBe("scan-scan-1-results.csv");
    expect(content.split("\n")[0]).toContain("attack_name,category,technique,template_id,verdict");
    expect(content).toContain("Inbox leak");
    expect(content).not.toContain("Direct override");
  });
});
