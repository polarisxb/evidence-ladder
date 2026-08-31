---
title: "Re-Test, Don't Re-Judge: Evidence-Stratified Measurement of Attack Success in Black-Box LLM Applications"
author: "Zihao Xu (Independent)"
venue: "Target: IEEE Conference on Secure and Trustworthy Machine Learning (SaTML)"
status: "Pre-registration draft — formal results pending (marked [TBD])"
version: "draft-en, prereg v2"
---

# Re-Test, Don't Re-Judge: Evidence-Stratified Measurement of Attack Success in Black-Box LLM Applications

> **Draft status.** This document is a pre-registration draft prepared for submission to SaTML. It fixes the measurement design, the primary estimand, and the analysis plan *before* the formal experiment is run. Every quantity that depends on the formal pilot is written as `[TBD]` and will be filled in only after data collection under the frozen protocol.

## Abstract

Attack-success rate (ASR) is the headline number in black-box LLM security evaluation, yet it is almost always produced by a single source — typically an LLM-as-a-Judge reading one `(payload, response)` transcript. Recent work shows this number is fragile: judges behave near-randomly under adversarial distribution shift, swapping the evaluator can move reported ASR by tens of points, and text alone cannot distinguish a claimed action from an executed one. The common remedy is to *re-judge*: correct the judge's precision, or swap in a second judge. We argue this cannot work in principle. Re-judging re-reads a fixed transcript and cannot manufacture evidence the transcript never contained. Only *re-testing* — issuing new queries, running matched controls, and probing business state — can gather independent evidence. We therefore propose **evidence-stratified measurement**: attack outcomes are partitioned by evidence source and strength on a six-rung ladder (E0 not-evaluable, E1 text-claim, E2 judge-suspected, E3 rule-verified, E4 tool-observed, E5 probe-verified), each logical case is run as a **Quartet** (Clean / Attack / Quoted Attack / Benign Distractor), and weak or conflicting findings trigger a conflict-driven **retest loop**. To isolate the effect of re-testing from re-judging, we run three arms over one frozen suite and one set of cached first responses: **Arm A** (judge-only, capped at E2), **Arm A'** (an independent re-judge of the same transcript, also capped at E2), and **Arm B** (the retest loop, which gathers new evidence and can climb from E0 to E5). Our **primary estimand** is the paired reduction in per-case measurement error of Arm B relative to Arm A, assessed with McNemar's test on discordant pairs against ground truth; the headline effect for the abstract is Arm B's **strong-evidence ASR (E3–E5)**. Secondary measures include an approximate-leak metric (`encoded_leak`, deliberately *not* promoted to E3), overturn and evidence-upgrade rates, extra-query cost, utility, and over-defense. On the formal pilot, Arm B reduces per-case error versus Arm A by `[TBD]` (McNemar `p = [TBD]`) and reports a strong-evidence ASR of `[TBD]`, while Arm A' — a second opinion with no new evidence — does not (`[TBD]`). The design is pre-registered; the analysis plan, abstention policy, and target contract are fixed in advance.

## 1. Introduction

### 1.1 The measurement problem

LLM applications are now deployed at the interface between untrusted input and privileged action: they read user messages, retrieved documents, tool outputs, and prior turns, and they can call APIs that send email, move money, or mutate records. Security evaluation of such systems almost always collapses to a single scalar — the attack-success rate — and that scalar is almost always produced by a single evidence source. In the dominant pipeline an attack payload is sent once, one response is captured, and an LLM-as-a-Judge decides whether the attack "succeeded." The number that reaches a report, a leaderboard, or a purchasing decision inherits every weakness of that one judge on that one transcript.

A line of 2026 work has made those weaknesses concrete rather than hypothetical. *A Coin Flip for Safety* (arXiv:2603.06594) shows, with thousands of human labels, that LLM judges approach chance accuracy under adversarial distribution shift, so that many "high-ASR" attacks are in fact exploiting judge false positives rather than real target vulnerabilities. *When Scanners Lie* (arXiv:2603.14633) holds the model outputs fixed and swaps only the evaluator, and finds reported ASR drifting by up to ±33% across 22 of 25 attack categories in a widely used open-source scanner. *Kill-Chain Canaries* (arXiv:2603.28013) argues that in multi-step and multi-agent settings a single final-response check is the wrong unit of analysis, because an attack propagates through stages (exposed, persisted, relayed, executed) that a text judge never sees. The application layer tells the same story from the other side: *GroundEval* replaces the judge with a deterministic state contract; *SafeClawBench* reports semantic acceptance, audit-visible evidence, and sandbox-state harm as three separate endpoints; *False Success* documents that "claimed done" and "environment actually changed" diverge even on non-adversarial tasks and that text judges have low AUROC for the difference; and *ASSERT* insists that every reported rate be bound to a written measurement specification.

### 1.2 Re-judging cannot manufacture evidence

Faced with an unreliable judge, the field's instinct is to fix the judge. *A Coin Flip for Safety* scales judge-positive results by an estimated judge precision to obtain a "Corrected ASR." Ensemble and swap strategies replace one judge with several. These are valuable, but they share a structural ceiling: they all *re-judge* — they re-read the same frozen `(payload, response)` pair. If the first response never contained decisive evidence (an exact secret, a tool call, a changed record), no amount of re-reading can create it. A more careful judge can lower confidence, an ensemble can average opinions, and a precision correction can rescale a rate, but none of them observes anything the transcript did not already contain. Re-judging can reduce *variance* in the interpretation of fixed evidence; it cannot reduce the *bias* that comes from missing evidence.

Our thesis is a single word swap: **re-test, don't re-judge.** When a finding is weak or self-contradictory, the correct next step is not another opinion on the same transcript but a new observation on a different channel — send the matched Quoted-Attack control to see whether mere quotation also "succeeds," re-issue a canary probe to see whether a purported secret is really disclosed, or execute a state probe to see whether a claimed action actually changed the business state. Each of these costs additional queries, and each returns evidence the original transcript did not contain. The empirical question this paper pre-registers is whether that extra evidence measurably reduces measurement error relative to both a single judge and a second judge — and it is engineered so that the difference between re-testing and re-judging is the only thing that varies.

### 1.3 Contributions

This paper makes the following contributions.

1. **An evidence-stratified success measure (E0–E5).** We replace the success boolean with a six-rung ladder that partitions outcomes by *source and strength* of evidence rather than collapsing them, so that a judge's suspicion (E2), an exact rule hit (E3), an over-privileged tool call (E4), and a probe-confirmed state change (E5) are never recorded as the same event.

2. **A Quartet control design.** Every logical case is run as four matched variants — Clean, Attack, Quoted Attack, Benign Distractor — that jointly expose quoted-attack false positives and over-defense, the two failure modes a single Attack run cannot separate.

3. **A three-arm identification design.** Over one frozen suite and one cache of first responses, Arm A (judge-only), Arm A' (independent re-judge), and Arm B (retest loop) differ only in mode. This isolates the effect of *re-testing* from the effect of merely *re-judging*, which prior work conflates.

4. **A conflict-driven retest loop with an audited lineage.** A `conflict_type → retest_action` state machine turns each weak finding into a targeted new observation, records the full `initial → retest_k → final` history, and finalizes each case as confirmed, overturned, or manual-review.

5. **A pre-registered estimand and analysis plan.** The primary estimand is the paired per-case error reduction of Arm B over Arm A, tested with McNemar; the abstention policy, the approximate-leak metric, the stateful target contract, and the ground-truth sources are all fixed in advance.

### 1.4 Scope, threat model, and pre-registration

We study black-box evaluation of deployed LLM applications under authorized red-teaming: the evaluator sends inputs and observes outputs, tool-call logs where exposed, and — for targets we control — business state, but has no access to weights or hidden prompts. The attack families in scope are direct prompt injection, system-prompt extraction, jailbreak, information disclosure, indirect injection, and excessive agency (agent over-privilege). We make no first-to claims; evidence stratification, deterministic confirmation, and kill-chain decomposition all exist in prior work, and our design is explicitly situated against it. What we contribute is the specific separation of re-testing from re-judging and a measurement whose every reported rate carries the evidence rung and the declared policy under which it was produced. Because our central claim is a claim about measurement, the protocol is pre-registered: the suite is content-hashed and seeded, the arms are fixed, and the formal quantities (`[TBD]` throughout) are reported only after the frozen run.

## 2. Method Overview

### 2.1 Multi-source evidence stratification (E0–E5)

Evidence-Ladder partitions each outcome by the strongest independent evidence observed for it. The rungs are defined so that strength increases monotonically with independence from the judge's opinion.

| Level | Name | Verification basis |
|---|---|---|
| E0 | Not Evaluable | Infrastructure failure, protocol error, target unreachable, or a declared judge abstention |
| E1 | Text Claim | The model only *states* in text that it executed the objective |
| E2 | Judge-Suspected | The LLM-as-a-Judge believes the attack succeeded, with no corroboration |
| E3 | Rule-Verified | Exact canary-token match / unique hidden-string disclosure / strong deterministic rule hit |
| E4 | Tool-Observed | A tool-call log shows an over-privileged invocation *attributable to the attack* |
| E5 | Probe-Verified | A business-state diff or probe query confirms the side effect actually occurred |

Two design rules keep the ladder honest. First, stronger evidence outranks weaker: a probe-verified breach stays E5 even if the judge abstained, and an exact rule hit stays E3 even if the judge called the case benign; the arbiter never lets a weak signal erase a strong one. Second, weak signals are never silently promoted. A canary token that appears only *quoted* in a refusal is E1, not E3; a bare tool call with no attack attribution is flagged `tool_without_provenance` rather than counted as E4. The E3 rung is reserved for exact, auditable matches precisely so that "strong evidence (E3–E5)" means what it says.

**Abstention as a declared parameter.** When the judge declines to rule and nothing stronger fired, the outcome is genuinely undetermined. How that case scores is a *declared parameter of the measurement*, recorded on every assessment. Our **primary** policy is `e0`: an abstention means "cannot tell," so the case is dropped from the denominator rather than counted as a clean negative. We report an `e2` **sensitivity** analysis, under which an abstention counts as a weak (E2) positive, to bound the effect of the choice; a legacy `negative` policy is retained only for re-scoring historical runs. No ASR in this paper is reported without its abstention policy attached.

**Approximate leaks (`encoded_leak`), deliberately not E3.** Real exfiltration is often obfuscated: a model may emit a secret Base64-encoded, ROT13-encoded, homoglyph-substituted, reversed, or whitespace-interleaved, so that an exact rule match fails even though information leaked. We detect these as a **secondary** `encoded_leak` metric. Because the match is approximate and requires decoding or fuzzy alignment, it is *not* promoted to E3; at most it raises a `secret_disclosure_suspected` conflict that the retest loop resolves with an exact canary re-test. This keeps E3 a clean, false-positive-free rung while still surfacing obfuscated disclosure as its own reported quantity.

### 2.2 Quartet four-way control

Each logical case is executed as four matched variants so that confounders are measured, not assumed away:

- **Clean** — the ordinary task input, measuring *utility* (does the app still work?).
- **Attack** — the input carrying the attack objective, measuring *attack success*.
- **Quoted Attack** — the identical attack content presented as quoted or analyzed text, isolating the *quoted-attack false positive* in which a judge mistakes discussion for execution.
- **Benign Distractor** — harmless but lexically similar long text, exposing *over-defense* (refusing safe inputs that merely look adversarial).

A safe and usable application should satisfy: Clean succeeds, Attack fails, Quoted Attack is not scored as success, and Benign Distractor is not refused. The Quoted-Attack and Benign-Distractor variants are what let the retest loop distinguish a real breach from a judge artifact.

### 2.3 Three arms: isolating re-testing from re-judging

The core experiment runs three arms over the **same** frozen suite and the **same** cached first responses, differing only in mode. This is what turns "re-test, don't re-judge" from a slogan into an identified comparison.

- **Arm A (judge-only).** The verdict comes from the first judge alone; no retest action is ever dispatched. The evidence level is capped at E2.
- **Arm A' (re-judge).** An *independent* verifier re-scores the same fixed `(payload, response)`. It contributes a second judge opinion but reads no new observation, dispatches no retest action, and is likewise capped at E2. Arm A' is the honest steel-man of "just use a better/second judge."
- **Arm B (retest loop).** On weak or conflicting findings, Arm B gathers *new* evidence by re-executing controls and probes, and can therefore climb from E0 all the way to E5.

Because A, A', and B consume identical inputs, any difference between A' and B is attributable to new evidence rather than to a different opinion — exactly the contrast the paper is about. Arm A' is constructed so that it cannot beat Arm B by construction: it never executes a probe, so it can neither overturn a judge false positive that only a control run reveals nor upgrade a weak-but-true text claim that only a state probe can confirm.

### 2.4 Conflict-driven retest loop

Weak findings are not left as weak findings; they are routed to a targeted new observation by a `conflict_type → retest_action` state machine. The main transitions are:

| `conflict_type` | Trigger condition | Retest action |
|---|---|---|
| `judge_without_rule_evidence` | Judge asserts success but no rule/probe evidence exists | Run the Quartet retest |
| `quoted_attack_success` | The Quoted-Attack control also "succeeds" | Flag as a judge false-positive candidate |
| `secret_disclosure_suspected` | Suspected leakage (incl. `encoded_leak`) without an exact canary hit | Run an exact canary re-test |
| `text_claim_requires_probe` | A text-only action claim with no tool log | Run a state probe |
| `clean_failed` | The Clean task itself fails | Mark `not_evaluable` / utility failure |

Each finding carries an auditable lineage (`initial → retest_1 → … → final`) and is finalized as **confirmed**, **overturned**, or **manual-review**. Confirmation and overturning are both first-class outcomes: Arm B upgrades a weak-but-true E1 text claim to E5 when a probe confirms the side effect, and it overturns an E2 judge suspicion when the matched Quoted-Attack control succeeds identically (showing the payload was not the cause). Every retest costs queries, which we report rather than hide.

### 2.5 Targets, estimand, and analysis plan

**Stateful target (v2); v1 sealed.** The E4 and E5 rungs require a target whose business state actually changes as a function of the model's action, so that a probe can verify a *real* side effect. Our **v2** design is stateful in exactly this sense: recorded business state reflects the model's tool invocation, and the E5 probe queries that state. An earlier **v1** canary-echo design shared ground-truth signal with judge-visible canary behavior and is therefore **construct-invalid** for a judge-error-correction claim. We **seal v1**: its runs are retained for provenance and audit but are excluded from the primary estimand and from every E4/E5 rate. All formal E4/E5 evidence in this paper is produced against the v2 stateful contract.

**Primary estimand.** For each in-scope attack case we assign a binary correctness label to Arm A and to Arm B by comparing each arm's success assertion to ground truth (an *error* is any disagreement). The primary estimand is the **paired reduction in per-case measurement error of Arm B relative to Arm A**, evaluated with **McNemar's test** on the discordant pairs (A-correct/B-wrong versus A-wrong/B-correct), using the exact binomial form for small discordant counts. We report the discordant counts, the McNemar statistic, and the net error reduction with a bootstrap confidence interval (≥1000 resamples). Ground truth comes from the v2 target's observable business state for observable cases and from a human-gold subset for the remainder; judge–human agreement is reported as Cohen's κ. The same comparison against Arm A' quantifies how much of any improvement is attributable to re-testing rather than re-judging.

**Headline and secondary reporting.** The abstract's headline effect is Arm B's **strong-evidence ASR (E3–E5)** — the fraction of attack cases confirmed at rule, tool, or probe strength. Alongside it we report, per arm with bootstrap 95% CIs: Judge ASR, attack false-positive rate, overturn rate, evidence-upgrade rate, extra-query cost, utility rate (Clean), over-defense rate (Benign Distractor), the secondary `encoded_leak` rate, and the `e2` abstention sensitivity beside the `e0` primary. Evidence-Stratified ASR is mathematically orthogonal to the Corrected ASR of *A Coin Flip for Safety*: Corrected ASR rescales a single source by an estimated precision, whereas our measure partitions by heterogeneous sources with no scaling and no source fusion, so the two can be reported side by side as complementary diagnostics.

**Expected results (pre-registered, `[TBD]`).** Under the frozen protocol we expect, and will report: Arm B reduces per-case error versus Arm A by `[TBD]` (McNemar `p = [TBD]`; discordant pairs `[TBD]`); Arm B's strong-evidence ASR is `[TBD]` versus `[TBD]` for Arm A; Arm A' matches Arm A within `[TBD]`, confirming that a second opinion without new evidence does not close the gap; Arm B's attack false-positive rate is `[TBD]` (overturns `[TBD]` of Arm A's E2 positives) at an extra-query cost of `[TBD]` per case; `encoded_leak` surfaces `[TBD]` obfuscated disclosures that no E3 rule caught; and the `e0`→`e2` sensitivity shifts headline ASR by `[TBD]`. The formal pilot covers ≥150 stateful attack cases under a seeded, content-hashed suite, with a human-annotated calibration subset for κ.

## 3. Related Work

*[TBD — see README §三 comparison table; REDAgentBench row to be added after citation verification]*

## 4. Experimental Setup

*[TBD — copy from `formal_pilot_protocol.v2.md` after suite hash frozen]*

## 5. Results

### 5.1 Exploratory findings (pre-v2)

- Judge self-inconsistency on byte-identical cached outputs: κ = 0.731 (`natural-3arm-block1`; single block, no human gold).
- Arm B recovered 3/3 positives dropped by re-judge and upgraded to E3 (n=3 mechanism demonstration).
- FP induction via fake placeholders failed: 0/8 false positives (`fp-probe-calib`).
- Stateful builtin mechanism demo: B corrected 16/16 initial errors vs A 50% error (`stateful_correction_builtin_dry_run`; synthetic, not natural rates).

### 5.2 Formal pilot (v2)

*[TBD]*

## 6. Limitations

*[TBD — see `docs/paper/pre-registration.zh-CN.md` §12 and exploratory caveats]*

## 7. Ethics

Authorized red-teaming only; synthetic canaries; no real user data. See `docs/evaluation_protocol.md` §13.

## 8. Conclusion

*[TBD after formal results]*
