---
name: project-conventions
description: >-
  Repository-wide architecture, coding conventions, and Cursor/Codex workflow
  expectations for the Evidence-Ladder (TianJian Libra internally) AI security
  testing platform. Use when working anywhere in this repository and you need
  guidance on project structure, module boundaries, evidence-protocol invariants,
  or repo-wide implementation rules.
---

# Project Conventions (Evidence-Ladder)

Use this skill as the repository-wide baseline whenever working in this project.
For specialized work, also load:

- `fastapi-patterns` for backend details
- `react-dashboard` for frontend details
- `attack-template-authoring` for attack template JSON edits
- `ai-security-knowledge` for security domain reasoning
- `superpowers-workflow` for any non-trivial change

## Repository identity

- **Public name**: Evidence-Ladder (`https://github.com/polarisxb/evidence-ladder`)
- **Internal/contest alias**: TianJian Libra / 天鉴 · 衡 (kept locally; suppressed in public-facing artifacts until the contest fully closes)
- **Author**: Xu Zihao (徐子豪) · GitHub `@polarisxb`
- **License**: MIT (Copyright 2026)
- **Versioning**: Semantic versioning, milestones tracked as Git tags (`v0.1.0`, `v0.2.0`, ...)

## Repository scope

This project is an **application-layer LLM security testing platform** focused on:

- prompt injection (direct + indirect)
- system prompt leakage (with canary-token verification)
- sensitive information disclosure
- jailbreak behavior
- excessive agency / unauthorized tool action
- evidence-stratified attack-success measurement (the methodology the paper is built on)

Out of scope: base-model adversarial robustness benchmarking (this is what
HarmBench / JailbreakBench / Coin Flip do — we cite, we don't compete head-on).

## Repository structure

```text
ai-security/
├── backend/                     # Python 3.11+ / FastAPI / SQLAlchemy async
│   └── app/
│       ├── api/                 # Route handlers (thin)
│       ├── attack_templates/    # JSON attack payloads (see attack-template-authoring)
│       ├── core/                # Cross-cutting helpers
│       ├── models/              # SQLAlchemy ORM models
│       ├── schemas/             # Pydantic request/response models
│       └── services/            # Business logic (evidence_arbiter, autotest_*, scan_runner, ...)
├── frontend/                    # React 18 + TypeScript + Vite + Tailwind
│   └── src/
│       ├── api/                 # API clients (one file per domain)
│       ├── components/          # Reusable components + layout
│       ├── hooks/               # Custom hooks
│       ├── pages/               # Page components
│       ├── types/               # Shared TypeScript types
│       └── utils/               # Utility functions
├── docs/
│   ├── opening_report.zh-CN.md  # Academic opening report
│   ├── evaluation_protocol.md   # The evaluation protocol the paper formalizes
│   ├── research/                # Literature matrix + research gap analysis
│   ├── dev-notes/               # Phase plans, design notes
│   └── papers/                  # Reference papers (PDFs are gitignored)
├── mock_targets/                # Local vulnerable targets for end-to-end testing
├── docker-compose.yml
└── README.md
```

## Repository-wide rules

- Prefer targeted, compatibility-aware changes over broad refactors unless the task explicitly requires otherwise.
- Keep backend business logic in `services/`, not in route handlers.
- Keep request/response contracts in `schemas/`.
- Keep frontend API access in `frontend/src/api/`.
- Keep reusable frontend types in `frontend/src/types/`.
- Prefer ASCII in new code files unless the file already uses Unicode or the content clearly requires it.
- Documentation files may freely use Chinese (`*.zh-CN.md`) and English (`*.en.md` or `*.md`).

## Backend conventions (Python)

- Type hints on all function signatures (params + return).
- All DB and IO operations are `async`.
- Pydantic v2 for request/response shapes.
- Custom `AppException` for domain errors; `raise HTTPException` only at the route layer.
- Configuration via `pydantic-settings` (`backend/app/config.py`); secrets in `.env`, never committed.
- Logging via `logger = logging.getLogger(__name__)`.

## Frontend conventions (TypeScript)

- Strict TypeScript; no `any` unless localized and justified.
- Function components + hooks; class components are forbidden.
- All API calls live under `src/api/`.
- All shared types live under `src/types/`.
- TailwindCSS for styling; no custom CSS unless absolutely necessary.
- Dark theme is the default.

## Evidence-protocol invariants (DO NOT BREAK)

These fields/contracts are research output. Touch them only with deliberate migration:

| Field / Concept | Where | Invariant |
|---|---|---|
| `evidence_level` (E0–E5) | `evidence_arbiter.py` + result schemas | The 6-level ladder is the public protocol. Adding a level requires opening-report + protocol doc updates. |
| `blackbox_outcome` | result schemas | Enum values stable across releases |
| `behavior_flags` | result schemas | Add flags, don't remove |
| `verdict_status` | result schemas | Never set directly from a Judge call without going through the arbiter |
| `business_verification_status` | adapter/probe result | Probe-verified status must come from an actual probe run |
| `quartet_present` | scan summary | Quartet variant linkage must remain queryable |
| `source_scan_id` (retest chain) | retest_runs | Retest history must remain auditable |

## Security testing rules

- Preserve evidence fields when modifying scan, analysis, or report flows.
- Do not weaken traceability just to simplify storage or UI.
- Prefer explicit, inspectable protocol fields over opaque blobs once a contract is stable.

## Cursor/IDE workflow rules (replaces old `.cursor/rules/cursorfather.mdc`)

The historical `cursorfather.mdc` rule depended on a specific MCP runtime
(`check_messages` / `ask_question` from a custom server) that is **not always
available** in this Cursor environment. The repo no longer treats those calls
as mandatory.

Equivalents that are always available:

- Use `TodoWrite` for multi-step work.
- Use direct, concise text replies for status updates.
- Use the built-in `AskQuestion` tool only when the user truly needs to choose between options; do not use it as a session-end ritual.
- Do not spawn sub-agents unless the user explicitly asks for delegation.

If the optional MCP tools (`check_messages`, `ask_question`, `save_progress`,
`load_progress`) are present in the active session, follow the rules in
`.cursor/rules/cursorfather.mdc` and `.cursor/rules/my-mcp.mdc`. Otherwise
ignore them.

## Before changing any persisted-data behavior

For changes touching the scan or report pipeline, in this order:

1. Identify the persisted data model involved (`backend/app/models/*.py`).
2. Identify the API response shape that depends on it (`backend/app/schemas/*.py` and `backend/app/api/*.py`).
3. Identify which frontend page consumes that shape (`frontend/src/pages/*.tsx`).
4. Preserve compatibility unless the task explicitly allows a breaking change.
5. If the change is breaking, plan a migration path and announce it in the opening report or release notes.

## Cross-references

- Mirror Codex skill (kept in sync): `.codex/skills/project-conventions/SKILL.md`
- Workflow coordinator: `.cursor/skills/superpowers-workflow/SKILL.md`
- Verification gate: `.cursor/skills/verification-before-completion/SKILL.md`
- Opening report: `docs/opening_report.zh-CN.md`
- Evaluation protocol: `docs/evaluation_protocol.md`
