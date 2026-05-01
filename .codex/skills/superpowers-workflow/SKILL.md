---
name: superpowers-workflow
description: >-
  Project-adapted Superpowers-style engineering workflow for this AI security
  testing platform. Use when the user mentions Superpowers, asks for a
  disciplined coding workflow, starts a broad feature/change, or wants
  brainstorm/spec/plan/test-first/review/verification discipline across backend,
  frontend, attack templates, or LLM integrations.
---

# Superpowers Workflow

## Intent

Use this as the project-level coordinator for a Superpowers-style workflow. It
adapts the upstream Superpowers methodology to this repository instead of
vendoring the upstream skill pack.

Always combine this skill with `$project-conventions`. Load narrower project
skills only when the task touches their area.

## Operating Contract

1. Frame the request before implementation.
   - State the target behavior, likely affected surfaces, assumptions, and
     non-goals.
   - Ask only when the decision is truly ambiguous or destructive.

2. Map the repository surface.
   - Backend API/service/schema/model work: use `$fastapi-patterns`.
   - Frontend dashboard/view/API-client work: use `$react-dashboard`.
   - Visual UI redesign: add `$frontend-design`.
   - Attack template changes: use `$attack-template-authoring` and
     `$ai-security-knowledge`.
   - LLM analyzer or OpenAI-call changes: use `$openai-integration` and
     `$ai-security-knowledge`.
   - Bug, regression, or failing test: use `$systematic-debugging`.

3. Plan before code.
   - For small tasks, keep the plan in `update_plan`.
   - For broad, durable, or resumed work, write PRD/test-spec artifacts under
     `.omx/plans/` when the active workflow requires it.
   - Keep each implementation slice independently verifiable.

4. Test before implementation when behavior changes.
   - Add or identify the regression test that proves the behavior.
   - Run the failing test first when feasible.
   - For cleanup/refactor work, lock existing behavior before edits.

5. Execute in narrow slices.
   - Prefer existing repository helpers and boundaries over new abstractions.
   - Preserve scan/report evidence fields and API compatibility unless the task
     explicitly allows a breaking change.
   - Use parallel agents only when the active environment and current
     instructions allow it, and only for disjoint tasks with clear ownership.

6. Review before claiming completion.
   - Self-review against the plan and repository conventions.
   - For larger or riskier changes, run a code-review pass before final
     verification.
   - Critical correctness, data-loss, auth, security, or compatibility findings
     block completion.

7. Verify with evidence.
   - Use `$verification-before-completion` before any completion claim.
   - Run the smallest command set that proves the changed behavior.
   - Report the commands run, their result, changed files, and any remaining
     risks.

## Phase Checklist

Use this lightweight sequence unless another active workflow gives a stricter
one:

```text
frame -> inspect -> spec/plan -> test-first -> implement -> review -> verify -> report
```

If the task is tiny and low risk, compress the sequence, but do not skip
inspection or verification.

## References

- Read `references/upstream-map.md` when mapping upstream Superpowers concepts
  to this repository's existing skills and OMX conventions.
