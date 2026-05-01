# Cursor Rules to Codex Mapping

This repository keeps the original `.cursor/rules` files for reference, but
their Codex-usable equivalents now live under `.codex/skills`.

## Mapping

- `.cursor/rules/project.mdc`
  - migrated to `.codex/skills/project-conventions/`

- `.cursor/rules/backend-python.mdc`
  - absorbed into `.codex/skills/fastapi-patterns/`
  - repository-wide parts also reinforced in `.codex/skills/project-conventions/`

- `.cursor/rules/frontend-react.mdc`
  - absorbed into `.codex/skills/react-dashboard/`
  - repository-wide parts also reinforced in `.codex/skills/project-conventions/`

- `.cursor/rules/attack-templates.mdc`
  - migrated to `.codex/skills/attack-template-authoring/`
  - related domain context remains in `.codex/skills/ai-security-knowledge/`

- `.cursor/rules/cursorfather.mdc`
  - not copied verbatim because it depends on Cursor-specific MCP runtime behavior
  - its applicable intent was adapted into the `Codex-Native Workflow Mapping`
    section of `.codex/skills/project-conventions/SKILL.md`

## Notes

- Codex skills are project-level and live in `.codex/skills/`.
- UI metadata for skills lives in each skill's `agents/openai.yaml`.
- The migrated skills are intended to replace the old rule behavior for Codex
  usage in this repository.
