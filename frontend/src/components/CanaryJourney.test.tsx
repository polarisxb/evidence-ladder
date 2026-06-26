import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CanaryJourney } from "./CanaryJourney";
import type { CanaryObservation, CanaryProvenance } from "../types";

// Identity translator: keeps assertions decoupled from copy and lets us assert
// on the i18n keys the component reaches for.
const t = (key: string) => key;

const responseObs: CanaryObservation = {
  token: "CANARY-abc123",
  channel: "response_text",
  context: "quoted",
  evidence_level: "E1",
  kill_chain_stage: "recon",
  strength: "weak",
  excerpt: "...the secret CANARY-abc123 appears verbatim...",
};
const toolObs: CanaryObservation = {
  token: "CANARY-abc123",
  channel: "tool_call",
  context: "tool_invoked",
  evidence_level: "E4",
  kill_chain_stage: "exploit",
  strength: "strong",
  excerpt: "sendEmail(to=CANARY-abc123)",
};
const stateObs: CanaryObservation = {
  token: "CANARY-abc123",
  channel: "business_state",
  context: "state_persisted",
  evidence_level: "E5",
  kill_chain_stage: "impact",
  strength: "hard",
  excerpt: "db row id=42 contains CANARY-abc123",
};

const fullChain: CanaryProvenance = {
  observations: [responseObs, toolObs, stateObs],
  evidence_level: "E5",
  kill_chain_stage: "impact",
  is_quoted_only: false,
  strongest_channel: "business_state",
};

const quotedOnly: CanaryProvenance = {
  observations: [responseObs],
  evidence_level: "E1",
  kill_chain_stage: "recon",
  is_quoted_only: true,
  strongest_channel: "response_text",
};

describe("CanaryJourney", () => {
  it("renders all three channel stages", () => {
    render(<CanaryJourney provenance={fullChain} t={t} />);
    expect(screen.getByTestId("canary-stage-response_text")).toBeInTheDocument();
    expect(screen.getByTestId("canary-stage-tool_call")).toBeInTheDocument();
    expect(screen.getByTestId("canary-stage-business_state")).toBeInTheDocument();
  });

  it("marks reached stages enabled and unreached stages disabled", () => {
    render(<CanaryJourney provenance={quotedOnly} t={t} />);
    const reached = screen.getByTestId("canary-stage-response_text");
    const unreached = screen.getByTestId("canary-stage-tool_call");
    expect(reached).toHaveAttribute("data-reached", "true");
    expect(reached).toBeEnabled();
    expect(unreached).toHaveAttribute("data-reached", "false");
    expect(unreached).toBeDisabled();
    expect(unreached).toHaveTextContent("report.canaryJourney.notReached");
  });

  it("shows the quoted-only warning badge only when is_quoted_only is set", () => {
    const { rerender } = render(<CanaryJourney provenance={quotedOnly} t={t} />);
    expect(screen.getByText("report.canaryJourney.quotedOnly")).toBeInTheDocument();
    rerender(<CanaryJourney provenance={fullChain} t={t} />);
    expect(screen.queryByText("report.canaryJourney.quotedOnly")).not.toBeInTheDocument();
  });

  it("opens the strongest channel's detail panel by default", () => {
    render(<CanaryJourney provenance={fullChain} t={t} />);
    const detail = screen.getByTestId("canary-detail");
    expect(within(detail).getByText(stateObs.excerpt)).toBeInTheDocument();
    expect(within(detail).getByText(stateObs.token)).toBeInTheDocument();
  });

  it("toggles a stage's detail panel open and closed on click", async () => {
    const user = userEvent.setup();
    render(<CanaryJourney provenance={fullChain} t={t} />);
    // business_state is open by default (strongest channel).
    await user.click(screen.getByTestId("canary-stage-business_state"));
    expect(screen.queryByTestId("canary-detail")).not.toBeInTheDocument();
  });

  it("switches the detail panel when another reached stage is clicked", async () => {
    const user = userEvent.setup();
    render(<CanaryJourney provenance={fullChain} t={t} />);
    await user.click(screen.getByTestId("canary-stage-tool_call"));
    const detail = screen.getByTestId("canary-detail");
    expect(within(detail).getByText(toolObs.excerpt)).toBeInTheDocument();
    expect(within(detail).queryByText(stateObs.excerpt)).not.toBeInTheDocument();
  });
});
