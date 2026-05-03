# Cursor Skills (Evidence-Ladder)

This directory holds the Cursor-side mirror of project-level skills. Cursor IDE
discovers these via the `description` frontmatter and surfaces them to the
agent's system prompt automatically — no manual loading needed.

The same skill set is also maintained under `.codex/skills/` for Codex CLI
sessions. **Both directories are the source of truth and should stay in sync**;
see `.codex/README.md` §Sync Convention for the exact rule.

## Skill Map (12 skills)

| Skill | What it does | When it activates | Common companions |
|---|---|---|---|
| **superpowers-workflow** | Project-adapted Superpowers engineering workflow (frame → inspect → spec → test-first → implement → review → verify → publication-safety → report) | User says "Superpowers"; broad change; new milestone; pre-commit/pre-push | `project-conventions` + the matching domain skill + `verification-before-completion` |
| **project-conventions** | Repo-wide architecture, conventions, evidence-protocol invariants | Any non-trivial change in this repo | Always pair with one domain skill |
| **ai-security-knowledge** | OWASP LLM Top 10, attack categories, defense reasoning | Designing attacks, response analysis, risk mapping | `attack-template-authoring`, `openai-integration` |
| **attack-template-authoring** | JSON template schema, ID rules, Quartet variant hints | Editing `backend/app/attack_templates/**` | `ai-security-knowledge`, `fastapi-patterns` |
| **defense-in-depth** | Multi-layer validation, input boundaries | Fixing input-driven bugs, designing safety boundaries | `fastapi-patterns`, `systematic-debugging` |
| **fastapi-patterns** | Backend API/service/schema/model conventions | FastAPI route, service, model, async DB work | `project-conventions`, `defense-in-depth`, `verification-before-completion` |
| **frontend-design** | Visual style, layout, distinctive UI direction | New page or visual redesign | `react-dashboard` |
| **openai-integration** | Structured output, prompt engineering, cost control | LLM call, analyzer, prompt structure work | `ai-security-knowledge`, `fastapi-patterns` |
| **react-dashboard** | React page patterns, state flow, data display | Dashboard, results, reports, forms | `project-conventions`, `frontend-design`, `verification-before-completion` |
| **systematic-debugging** | Four-phase debugging, root cause before fix | Any bug, regression, failing test | `defense-in-depth`, `verification-before-completion` |
| **verification-before-completion** | Evidence-before-claim gate, fresh runs only | Pre-commit, pre-PR, pre-claim of "done" | All implementation skills |
| **article-writing** | Long-form content with consistent voice | Blog post, paper section, competition report draft | `superpowers-workflow` (for the Spec phase) |

## Quick task → skill recipes

### New backend feature
1. `project-conventions`
2. `fastapi-patterns`
3. `defense-in-depth`
4. `verification-before-completion`

### New frontend page
1. `project-conventions`
2. `react-dashboard`
3. `frontend-design`
4. `verification-before-completion`

### Broad / cross-stack work or new milestone slice
1. `superpowers-workflow`
2. `project-conventions`
3. The relevant domain skills
4. `verification-before-completion`

### Attack template / payload work
1. `attack-template-authoring`
2. `ai-security-knowledge`
3. `verification-before-completion`

### LLM analyzer / Judge / OpenAI call changes
1. `project-conventions`
2. `openai-integration`
3. `ai-security-knowledge`
4. `verification-before-completion`

### Any bug, regression, or failing test
1. `systematic-debugging`
2. `project-conventions`
3. Domain skill matching the bug surface
4. `verification-before-completion`

### Drafting paper section, README, blog post, competition report
1. `article-writing`
2. `project-conventions` (for facts)
3. `superpowers-workflow` (Spec phase if it's a long doc)

### Unsure where to start
1. `project-conventions`
2. Pick a domain skill by file location
3. Always end with `verification-before-completion`

## Default companion rule

Every non-trivial change implicitly loads:

- `project-conventions` — repo baseline
- `verification-before-completion` — completion gate

Add `superpowers-workflow` whenever the work touches more than one slice or
matters for a milestone.

## How to add a new skill

1. Create `.cursor/skills/<name>/SKILL.md` with `name:` + `description:` frontmatter
2. Mirror to `.codex/skills/<name>/SKILL.md` (same content, may add `Source:` line in frontmatter for upstream attribution)
3. Update both this index and `.codex/README.md`
4. Append the new entry under `.codex/RULES_MIGRATION.md` if it supersedes an old `.cursor/rules/*.mdc`

## Sync rule (must read)

**`.cursor/skills/<name>/SKILL.md` and `.codex/skills/<name>/SKILL.md` must
have functionally identical content.**

If one is changed, the other must be updated in the same commit.

A simple sanity check (Windows PowerShell):

```powershell
# Compare skill names present in both directories
$cursor = Get-ChildItem .cursor/skills -Directory | Select-Object -ExpandProperty Name
$codex  = Get-ChildItem .codex/skills  -Directory | Select-Object -ExpandProperty Name
Compare-Object $cursor $codex -PassThru
```

If any skill name appears only on one side, fix the divergence.
