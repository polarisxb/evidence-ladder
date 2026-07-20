---
name: superpowers-workflow
description: >-
  Project-adapted Superpowers-style engineering workflow for the Evidence-Ladder
  (TianJian Libra internally) AI security testing platform. Activate when the
  user mentions "Superpowers", asks for a disciplined coding workflow, starts a
  broad feature/change, kicks off a new milestone (v0.2 Pilot, v0.3 Cohen's κ,
  v0.4 Agent sandbox, v0.5 paper preprint), or wants brainstorm/spec/plan/
  test-first/review/verification discipline across backend, frontend, attack
  templates, evaluation protocol, or LLM integrations. Also activate when the
  user is about to commit, push, or publish anything academic-grade.
---

# Superpowers Workflow (Evidence-Ladder edition)

This is the project-level coordinator skill for a Superpowers-style engineering
workflow, adapted to the **Evidence-Ladder** (a.k.a. *TianJian Libra*) repository.

It is not a verbatim copy of upstream Superpowers — it is the local contract
for how disciplined work is done in this repo: **research-aware, publication-safe,
milestone-conscious, evidence-driven**.

Always combine this skill with `project-conventions`. Pull narrower skills only
when the task touches their area (see the §Skill Composition Map below).

---

## 0. Project context cheatsheet (read first)

The agent must know these facts before acting:

| Fact | Value |
|---|---|
| **Public name** | `Evidence-Ladder` (https://github.com/polarisxb/evidence-ladder) |
| **Internal/contest alias** | `TianJian Libra` / `天鉴 · 衡` (kept locally, not in public README until contest fully closes) |
| **Author** | Xu Zihao (徐子豪) · GitHub `@polarisxb` |
| **License** | MIT (Copyright 2026) |
| **Current version** | v0.1.0 (released 2026-05-02) |
| **Default branch** | `main` |
| **Tracking remote** | `origin → https://github.com/polarisxb/evidence-ladder.git` |
| **Test runner** | `python -m pytest backend\tests\` |
| **Frontend build** | `cd frontend && npm run build` |
| **Static check** | `python -m compileall -q backend\app` |
| **OS / shell** | Windows / PowerShell 5.x (UTF-8 quirks — see §6) |
| **Active worktree** | `worktree/superpowers-test` exists; main branch lives in `c:/all_project/ai-security` |

The repo has both engineering goals (a working LLM-application security testing
platform) and **academic goals** (a paper around Evidence-Stratified ASR + the
E-level × Kill-chain matrix, differentiated against *A Coin Flip for Safety*
(2026), *When Scanners Lie* (2026), *Kill-Chain Canaries* (2026)).

Every change must respect both.

---

## 1. The Phase Sequence

Use this default sequence unless a stricter workflow already governs the task:

```text
frame  ->  inspect  ->  spec/plan  ->  test-first  ->  implement
       ->  review   ->  verify     ->  publication-safety  ->  report
```

Tiny, low-risk tasks may compress phases, **but never skip `inspect`,
`verify`, or `publication-safety`** in this repo.

### 1.1 Frame
- State the target behavior, affected surfaces, assumptions, non-goals.
- For research/experimental tasks: state which `evidence_level` (E0–E5),
  ASR variant (Raw / Judge / Corrected / Verification-layer / Stratified /
  Quartet-Validated / Probe-Verified), or kill-chain stage is being measured.
- Ask only when truly ambiguous or destructive.

### 1.2 Inspect
- Map the repository surface using §3 Skill Composition Map.
- Read 2–4 anchor files before proposing edits.
- For data-touching changes, identify the persisted data model + API shape +
  consuming frontend page (per `project-conventions`).

### 1.3 Spec / Plan
- For small tasks, keep the plan in a TodoWrite or short bullet list.
- For broad work, write a planning doc under `docs/dev-notes/` using the
  existing `*_plan.zh-CN.md` style (see `autotest_agent_v1_superpowers_plan.zh-CN.md`
  as a reference).
- Each implementation slice must be independently verifiable.

### 1.4 Test-first
- For new behavior: add or identify the regression test before writing the
  implementation. Run the failing test first when feasible.
- For protocol/metric work: add the unit test for the boolean predicate
  (e.g., E3 detection rule) before changing the arbiter.
- For UI work: identify the smoke path you'll click through.

### 1.5 Implement
- Prefer existing helpers and module boundaries (see `project-conventions`).
- Preserve evidence fields: `blackbox_outcome`, `behavior_flags`,
  `verdict_status`, `rule_hits`, `business_verification_status`,
  `probe_summary`, `quartet_present`, `evidence_level`. **Never silently rename
  or drop these** without a deliberate migration plan.
- Preserve API compatibility for `/api/v1/scans/*` and `/api/v1/autotest/*`
  unless the task explicitly allows a breaking change.
- Use parallel sub-agents only when the active environment allows and the
  tasks are disjoint with clear ownership.

### 1.6 Review
- Self-review against the plan and §2 Project-specific gates.
- For non-trivial changes, do a review pass before final verification.
- Critical correctness, data-loss, auth, security, or research-integrity
  findings block completion.

### 1.7 Verify
- Run the smallest command set that proves the change.
- Use the `verification-before-completion` skill: evidence before claims,
  fresh runs only, full output read.
- For metric/statistical changes, run the dedicated tests:
  `python -m pytest backend\tests\test_evidence_arbiter.py backend\tests\test_autotest_metrics.py backend\tests\test_retest_policy.py`

### 1.8 Publication safety (Evidence-Ladder specific — MUST)
Before any `git push`, `git tag`, or release, verify:

- [ ] No participant ID (any pattern matching `\d{10}-参赛`) in tracked files
- [ ] No raw `*.env` (only `*.env.example`)
- [ ] No real API keys in attack templates, configs, or fixtures
- [ ] No real customer data, real user secrets, or unredacted canary tokens
- [ ] No `.cursor/mcp.json` (contains personal Windows paths)
- [ ] No `*.pdf` of third-party academic papers under `docs/papers/` (copyright)
- [ ] No `参赛总文件夹/` or `*-参赛总文件夹/` in tracked files (use `git ls-files "参赛总文件夹"` to check, **not** `Select-String 参赛` — see §6)
- [ ] If contest is **not yet fully closed**: no `天鉴` / `TianJian` / `JianHeng` strings in `README.md` / `README.en.md` / repo Description / repo Topics
- [ ] If contest **has fully closed**: code-level brand cleanup may proceed (see milestone v0.2.5)

### 1.9 Report
- Report commands run, their result, changed files, remaining risks.
- For research-touching work, also report which paper claim or which
  reviewer-anticipated question the change addresses.

---

## 2. Project-specific review gates

Before claiming completion, verify NONE of these red lines were crossed:

| Gate | What to check |
|---|---|
| **Evidence integrity** | E0–E5 ladder semantics preserved; never collapse multiple evidence sources into a single boolean for an existing field |
| **Judge non-supremacy** | LLM Judge result is never written into `verdict_status` as if it were ground truth; it stays a layer (`E2`) |
| **ASR plurality** | Never report a single "ASR" number without indicating its evidence source; reports must keep the multi-source split |
| **Quartet integrity** | Quartet variants are kept linkable (`source_case_id` chain); Quartet retest results don't overwrite originals |
| **Probe authenticity** | A probe-verified upgrade (`E5`) must come from an actual probe execution, not from a text claim |
| **Retest auditability** | Each finding's history `initial → retest_1 → ... → final` must be queryable |
| **Backward compatibility** | `/api/v1/scans/*` and `/api/v1/autotest/*` keep their existing JSON shape; add fields, don't remove |
| **Reproducibility** | Random seeds, model versions, prompt versions are recorded for any reported metric |
| **Differentiation** | New methodology must be defensible against *Coin Flip for Safety*, *Scanners Lie*, *Kill-Chain Canary* — see `docs/opening_report.zh-CN.md` §3.5 |

---

## 3. Skill Composition Map

When the task touches an area, also load the matching skill:

| Task surface | Add this skill |
|---|---|
| Backend API / service / schema / model | `fastapi-patterns` |
| Frontend dashboard / view / API client | `react-dashboard` |
| Visual UI redesign or new page aesthetics | `frontend-design` (in addition to `react-dashboard`) |
| Attack template JSON edits | `attack-template-authoring` + `ai-security-knowledge` |
| LLM analyzer / OpenAI / structured output | `openai-integration` + `ai-security-knowledge` |
| Bug, regression, failing test | `systematic-debugging` |
| Adding input validation / safety boundary | `defense-in-depth` |
| Writing the paper / preprint / blog post | `article-writing` |
| Pre-commit / pre-PR / pre-release verification | `verification-before-completion` (always) |

For any non-trivial change: `project-conventions` is implicit baseline +
`verification-before-completion` is implicit gate.

---

## 4. Milestone awareness

Match the current task to the active milestone so the agent picks the right
slice and the right verification depth.

| Milestone | Status | What's in scope | What's out of scope |
|---|---|---|---|
| **v0.1** | ✅ Released 2026-05-02 | Core framework, AutoTest Agent v1, public release | (locked) |
| **v0.2** Pilot Data | 🟡 In progress | 30-case Pilot generator, batch experiment runner, Coin Flip / Scanners Lie baselines, results CSV + LaTeX export, manual-annotation UI, Cohen's κ + Bootstrap CI, first comparison figure | Large benchmarks, multi-agent sandbox |
| **v0.2.5** Brand Cleanup | ⏸ Waiting (contest closure) | Replace 36 occurrences of `天鉴` / `TianJian` / `JianHeng` in code and UI with `Evidence-Ladder`; rename `JianHengLogo.tsx`; add `Chinese alias: 天鉴·衡 (early contest codename)` line back into README | Methodology changes |
| **v0.3** Formal Experiments | 🔜 Planned | 100+ cases × 3–5 models, double-annotated 200+ findings, Cohen's κ ≥ 0.6 enforcement, multiple-comparison correction, full reproducibility bundle | Agent sandbox build-out |
| **v0.4** Agent Sandbox | 🔜 Planned | Email + e-commerce minimal agent sandboxes, Kill-chain stage tracker (Exposed / Persisted / Relayed / Executed), 5×4 E×K matrix experiments | Cross-domain generalization |
| **v0.5** Paper Preprint | 🔜 Planned | arXiv preprint, public dataset release, BibTeX, dataset DOI | Conference-ready camera-ready |
| **v0.6** Submission | 🔜 Planned | Target venue selection, response to reviews | New methodology |

When unsure which slice to take, ask: *"Which artifact in the active milestone
does this advance?"*

---

## 5. Commit / release rhythm

- Use Conventional Commits style: `feat:`, `fix:`, `chore:`, `refactor:`,
  `docs:`, `test:`, `experiment:`, `data:`.
- Keep commit subject ≤ 72 chars; use `-m "subject" -m "body"` for multi-line.
- Tag every released milestone: `vMAJOR.MINOR.PATCH` (e.g., `v0.2.0`).
- Never force-push to `main` unless explicitly authorized by the user.
- Never amend or rewrite a commit that has been pushed unless explicitly
  authorized.
- For experiment-result commits, prefer `experiment:` prefix and include the
  model, sample count, and seed in the commit body.

---

## 6. PowerShell / Windows / git gotchas

This repo lives on Windows + PowerShell 5.x. Several real bugs have been
caused by these gotchas — always assume them:

| Gotcha | Workaround |
|---|---|
| `Select-String 参赛` / `findstr 参赛` may silently miss matches due to ANSI/UTF-8 mismatch | Use `git ls-files "<chinese-folder>"` for tracked-file matching, or write to UTF-8 file then `Get-Content -Encoding UTF8 | Select-String` |
| `git status` does not surface already-tracked files; a folder added in an earlier commit will not appear after adding `.gitignore` rules | Use `git ls-tree -r HEAD --name-only` to inspect what's actually in the tree, and `git rm -r --cached <folder>` to untrack |
| `head`, `tail`, `cat` are not native PS commands | Use `Select-Object -First N`, `Get-Content -Tail N`, `Get-Content` (or use the Read tool) |
| `&&` chaining is not supported in PowerShell 5.x | Use `;` for sequential, or wrap in `if ($?) { ... }` for conditional |
| Multi-line `-m` strings to `git commit` may break | Use `-m "subject" -m "single-line body"` (no newlines inside `-m`) or write to a file and use `-F` |
| Git emits LF→CRLF warnings; these are not errors | Ignore unless `core.autocrlf` is misconfigured |
| `git push --tags` pushes ALL local tags including backups | Use `git push origin <tag-name>` for a specific tag |
| Credential Manager 2.x triggers a browser login on first push | Block_until_ms ≥ 120000 when shell-running first push |

---

## 7. Cross-references

- Repository overview: `README.md` and `README.en.md`
- Evaluation protocol: `docs/evaluation_protocol.md`
- Opening report (Chinese): `docs/opening_report.zh-CN.md`
- Literature matrix: `docs/research/literature_matrix.zh-CN.md`
- Research gaps analysis: `docs/research/research_gaps_2024_2026.zh-CN.md`
- AutoTest Agent v1 plan: `docs/dev-notes/autotest_agent_v1_superpowers_plan.zh-CN.md`
- Mirror Codex skill (kept in sync): `.codex/skills/superpowers-workflow/SKILL.md`

If you change this skill, also update the Codex mirror (`.codex/skills/superpowers-workflow/SKILL.md`)
and the index files (`.cursor/skills/README.md` + `.codex/README.md`).

---

## 8. Anti-patterns

Reject these as invalid completions:

- "Tests should pass" — no fresh `pytest` output cited
- A new ASR number reported as a single boolean without source attribution
- A `verdict_status` set directly from a Judge call
- A retest result silently overwriting the original finding
- A push or release without going through the §1.8 publication-safety checklist
- Mentioning `天鉴` / `TianJian` in a public-facing artifact while the contest is still in evaluation
