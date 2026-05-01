# Superpowers to AI Security Project Map

This repository uses a project-adapted Superpowers workflow. Do not vendor the
upstream skill pack by default; use this map to reuse its discipline while
staying compatible with local Codex and OMX conventions.

## Upstream Workflow Mapping

| Superpowers concept | Project adaptation |
| --- | --- |
| `using-superpowers` | Use `$superpowers-workflow` as the project-level entry point, then route to narrower local skills. |
| `brainstorming` | Frame the request, clarify risky ambiguity, and record assumptions before code. Use concise `update_plan` items for active work. |
| `using-git-worktrees` | Use only when this is a git repository and isolation is useful. If no `.git` exists, continue in place and report that worktree isolation was not available. |
| `writing-plans` | Prefer `update_plan` for normal work. Use `.omx/plans/` PRD/test-spec artifacts for broad, persistent, or Ralph-gated work. |
| `test-driven-development` | Add or identify a regression test before behavior changes. Run the relevant failing test first when feasible, then implement the smallest passing change. |
| `subagent-driven-development` / `dispatching-parallel-agents` | Use Codex native subagents or OMX team mode only when current instructions allow it and tasks have disjoint ownership. Otherwise execute locally in slices. |
| `executing-plans` | Implement plan items sequentially unless independent tasks can safely run in parallel. Update plan status as work progresses. |
| `requesting-code-review` | For broad or risky changes, run a code-review pass focused on bugs, regressions, compatibility, security, and missing tests. |
| `receiving-code-review` | Treat review feedback as hypotheses to verify. Fix confirmed issues without blind rewrites. |
| `systematic-debugging` | Use the local `$systematic-debugging` skill for bugs, regressions, failures, and unexpected behavior. |
| `verification-before-completion` | Use the local `$verification-before-completion` skill before final status, commits, PRs, or delivery claims. |
| `finishing-a-development-branch` | Verify, summarize changed files, explain risks, and only perform merge/cleanup actions when requested and safe. |

## Project-Specific Gates

Backend changes:

- Confirm route/service/schema/model boundaries before editing.
- Keep business logic in `backend/app/services/`.
- Preserve API response compatibility unless the task explicitly changes it.

Frontend changes:

- Keep API access in `frontend/src/api/`.
- Keep shared contracts in `frontend/src/types/`.
- Verify the page state that consumes any changed API shape.

AI security changes:

- Preserve evidence and traceability fields in scan, analysis, and report flows.
- Prefer explicit protocol fields over opaque blobs once a contract is stable.
- For attack templates, keep IDs, categories, payloads, and success indicators consistent with `$attack-template-authoring`.

LLM/OpenAI changes:

- Prefer structured outputs and explicit error handling.
- Verify fallback behavior and cost-sensitive paths where practical.

Completion:

- Report changed files, simplifications made, verification commands, and remaining risks.
