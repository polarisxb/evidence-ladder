<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

# Evidence-Ladder

### Multi-Source Evidence-Stratified Evaluation for LLM Application Security

*Trustworthy attack-success measurement for LLM applications via multi-source evidence stratification (E0–E5) and conflict-driven retesting. **Beyond LLM-as-a-Judge.***

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Status: research-preview](https://img.shields.io/badge/status-research--preview-orange.svg)](#project-status)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Made for LLM Apps](https://img.shields.io/badge/scope-LLM%20applications-7c3aed.svg)](#scope)

[中文 README](./README.md) · [Evaluation Protocol](./docs/evaluation_protocol.md)

</div>

---

## 1. Motivation

Recent 2026 work has independently established that **single-source attack-success rates are unreliable** in LLM safety evaluation:

- *A Coin Flip for Safety* (arXiv:2603.06594) — LLM-as-a-Judge can perform near-randomly under adversarial distribution shift; many "high-ASR" attacks exploit judge false positives rather than true model vulnerabilities.
- *When Scanners Lie* (arXiv:2603.14633) — In open-source scanners (e.g., garak), 22 of 25 attack categories exhibit evaluator instability, with reported ASR drifting up to ±33% when the evaluator is swapped.
- *Kill-Chain Canaries* (arXiv:2603.28013) — In multi-agent systems, evaluation must decompose attacks across propagation stages (Exposed → Persisted → Relayed → Executed), not just inspect the final response.

These works identify the problem; they do not jointly solve it for **LLM applications** (RAG, tool-using agents, business-prompt configurations), where evaluation faces additional confounders: prompt assembly templates, retrieval context, post-processing, and tool/state side effects.

**Evidence-Ladder** addresses this gap with a black-box evaluation framework for the application layer.

## 2. Method overview

### 2.1 Multi-source evidence stratification (E0–E5)

Attack outcomes are partitioned by **evidence source and strength** rather than collapsed into a single boolean:

| Level | Name | Verification basis |
|---|---|---|
| E0 | Not Evaluable | Infrastructure failure, protocol error, or target unreachable |
| E1 | Text Claim | Model only verbally claims execution |
| E2 | Judge-Suspected | LLM-as-a-Judge believes the attack succeeded |
| E3 | Rule-Verified | Canary token / hidden string / strong rule hit |
| E4 | Tool-Observed | Tool-call log shows over-privileged invocation |
| E5 | Probe-Verified | Business-state diff or probe query confirms the side effect |

### 2.2 Quartet four-way control

Each logical attack case is tested in four variants to isolate confounders:

- **Clean** — normal task input (measures `Utility`).
- **Attack** — input containing the attack objective (measures `Attack Success`).
- **Quoted Attack** — attack content presented as quoted/analyzed text, isolating *quoted-attack false positives* where the judge mistakes "discussion" for "execution".
- **Benign Distractor** — harmless but lexically similar long text, exposing *over-defense*.

A safe-and-usable application should satisfy: Clean succeeds, Attack fails, Quoted Attack fails, Benign Distractor is not refused.

### 2.3 Evidence-Stratified ASR

Evidence-Stratified ASR (E-ASR) reports attack success **partitioned by source**:

- Raw ASR, Judge ASR, Text-Claim ASR, Rule-Verified ASR, Tool-Observed ASR, Probe-Verified ASR, Quartet-Validated ASR
- Plus: Evaluability Rate, Utility Rate, Over-Defense Rate

E-ASR is **mathematically orthogonal** to *Corrected ASR* (Coin Flip, 2026):

- Corrected ASR scales judge-positive results by judge precision (post-hoc correction of a single source).
- E-ASR partitions results by heterogeneous evidence sources (no scaling, no implicit scalar collapse).

Both can be reported side-by-side as complementary diagnostics.

### 2.4 Conflict-driven retest loop

Weak evidence findings automatically trigger retests via a `conflict-type → retest-action` state machine:

| `conflict_type` | Trigger condition | Retest action |
|---|---|---|
| `judge_without_rule_evidence` | Judge says success but rule/probe shows none | Run Quartet retest |
| `quoted_attack_success` | Quoted Attack also "succeeds" | Flag as judge false-positive candidate |
| `secret_disclosure_suspected` | Suspected leakage without canary hit | Run canary re-test |
| `unauthorized_action_claim` | Text-claim of action without tool log | Run probe verification |
| `clean_failed` | Clean task fails | Mark `not_evaluable` or `utility_failure` |

Each finding maintains an auditable retest history (`initial → retest_1 → ... → final`) and is finalized as `confirmed`, `overturned`, or `manual_review_needed`.

### 2.5 E-level × Kill-chain matrix

Evidence strength (E0–E5) is combined orthogonally with attack-propagation stage (Exposed / Persisted / Relayed / Executed) into a 5×4 evaluation matrix:

```
                Exposed     Persisted    Relayed     Executed
E1 Text-Claim    repeat       —          forward     claim
E2 Judge         judge        —          judge       judge
E3 Rule          canary-in    canary-mem canary-rel  canary-arg
E4 Tool          —            tool-write tool-read   tool-invoke
E5 Probe         —            state-snap state-diff  state-change
```

This matrix differentiates *"where the attack propagated"* from *"on what evidence we confirm it"*. A finding at (E5, Persisted) and another at (E1, Executed) carry very different operational risk, but a single-axis evaluation collapses them.

## 3. Differentiation from prior work

| Prior work | Their contribution | Our orthogonal contribution |
|---|---|---|
| *A Coin Flip for Safety* (2026) | Statistical post-hoc ASR correction via judge precision | Source-partitioned evidence ladder; no scaling |
| *When Scanners Lie* (2026) | Independent verifier as a second-stage check | Multi-class heterogeneous evidence + automated retest state machine |
| *Kill-Chain Canaries* (2026) | Single-axis attack-propagation decomposition | Two-axis E-level × Kill-chain matrix |
| HarmBench / JailbreakBench | Base-model adversarial robustness benchmark | Application-layer evaluation with business probes |
| AgentDojo / tau-bench / AgentHarm | Agent / tool-use benchmark | Evidence-stratified evaluation grounded in deployed-application surfaces |
| garak / PyRIT / Promptfoo / DeepTeam | Open-source LLM red-team toolkit | Reliability-aware reporting (E-ASR, Quartet, conflict-driven retest) |

Full literature analysis will be released with the paper.

## 4. Quick start

> Detailed installation and Chinese walkthrough live in the [Chinese README](./README.md).

```bash
# Backend (Python 3.11+)
cd backend
cp .env.example .env  # fill model/API config
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (Node.js 20+)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 for the dashboard, http://localhost:8000/docs for the API.

## 5. Reproducibility

This repository ships:

- Attack template library (`backend/app/attack_templates/`)
- Black-box adjudication services (`backend/app/services/verdict_*`, `evidence_arbiter.py`)
- AutoTest planning, retest policy, summary services (`backend/app/services/autotest_*`)
- Frontend dashboard (`frontend/`)
- Test suite (`backend/tests/`) — at least 35 tests covering planner, evidence arbiter, retest policy, AutoTest API, summary API
- Evaluation protocol (`docs/evaluation_protocol.md`)

The published experimental results, human-annotated calibration set, and per-model statistics tables (planned in the opening report §9) are **work in progress** and will be added as `docs/papers/` artifacts in subsequent releases.

## 6. Citation

A machine-readable [`CITATION.cff`](./CITATION.cff) is provided. GitHub renders a "Cite this repository" button automatically.

BibTeX:

```bibtex
@software{xu_evidence_ladder_2026,
  author       = {Xu, Zihao},
  title        = {Evidence-Ladder: Multi-Source Evidence-Stratified Evaluation for LLM Application Security},
  year         = {2026},
  version      = {0.1.0},
  url          = {https://github.com/polarisxb/evidence-ladder},
  license      = {MIT}
}
```

## 7. Project status

**Research preview (v0.1.0)** — framework, protocol, and platform implementation are functional. Experimental results, calibration set, and the academic paper draft are still being prepared.

Roadmap:

- v0.1 (current) — Framework, evaluation protocol, AutoTest agent v1, Quartet retest loop, summary API.
- v0.2 — Pilot experiment data (30 cases × 4 variants × 2 models), human-annotated calibration subset.
- v0.3 — Cross-model formal experiment (100+ cases × 3–5 models), Cohen's κ analysis, comparison against Corrected ASR / Verification-layer ASR baselines.
- v0.4 — E-level × Kill-chain matrix experiments on multi-agent sandboxes (mail / e-commerce).
- v0.5 — Public dataset release + paper preprint.

## 8. License

[MIT](./LICENSE).

## 9. Acknowledgments

Builds upon the open-source ecosystem of LLM safety evaluation: HarmBench, JailbreakBench, AgentDojo, tau-bench, ToolEmu, garak, PyRIT, Promptfoo, and the OWASP LLM Top 10 / Agentic Top 10. Differentiation analysis additionally cites the 2026 reliability literature: *A Coin Flip for Safety*, *When Scanners Lie*, *Kill-Chain Canaries*, *Noisy but Valid*, *Know Thy Judge*, and *RobustJudge*.
