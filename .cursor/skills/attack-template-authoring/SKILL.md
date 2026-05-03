---
name: attack-template-authoring
description: >-
  Repository-specific rules for authoring and updating attack template JSON
  files under backend/app/attack_templates. Use when creating, editing, or
  reviewing attack template categories, IDs, payloads, success indicators, or
  Quartet variant generation hints.
---

# Attack Template Authoring (Evidence-Ladder)

Use this skill when editing files under `backend/app/attack_templates/**/*.json`.

For attack semantics and category knowledge, also load:

- `ai-security-knowledge`

For repo-wide invariants, also load:

- `project-conventions`

## Template file shape

Each attack template JSON file has this top-level structure:

```json
{
  "category": "prompt_injection",
  "category_name": "Prompt Injection",
  "owasp_id": "LLM01",
  "description": "Category description",
  "templates": [
    {
      "id": "PI-001",
      "name": "Direct Instruction Override",
      "technique": "instruction_override",
      "severity": "high",
      "payloads": [
        {
          "text": "The actual attack text to send",
          "language": "en",
          "variant": "base"
        }
      ],
      "success_indicators": [
        "List of strings describing what success looks like"
      ],
      "multi_turn": false
    }
  ]
}
```

## ID naming rules

- Prompt Injection: `PI-001` to `PI-999`
- System Prompt Extraction: `SP-001` to `SP-999`
- Jailbreak: `JB-001` to `JB-999`
- Information Disclosure: `ID-001` to `ID-999`
- Indirect Injection: `II-001` to `II-999`
- Excessive Agency: `EA-001` to `EA-999`
- Multi-Turn (deprecated for new work; prefer category-specific IDs): `MT-001` to `MT-999`

## Required fields per template

- `id`
- `name`
- `technique`
- `severity` — one of `critical`, `high`, `medium`, `low`
- `payloads` — at least one
- `success_indicators` — at least one

## Authoring rules

- Keep payload text realistic for black-box testing (no academic toy phrasing).
- Keep `technique` names stable and machine-friendly (snake_case).
- Use `multi_turn: true` only when the template genuinely requires ordered turns.
- Keep category metadata aligned with the actual contents of the file.
- When adding a payload variant intended as Quartet `Quoted Attack` or
  `Benign Distractor`, set `variant` accordingly so the variant generator can
  pick it up.

## Quartet-aware variants

For templates that will participate in v0.2+ Quartet experiments, prefer providing:

- `variant: "base"` — the canonical attack payload (used as `Attack`)
- `variant: "quoted"` — the same payload wrapped as quoted/analyzed text (for `Quoted Attack`)
- `variant: "distractor"` — a benign payload of similar length/format (for `Benign Distractor`)

If the template doesn't ship `quoted` / `distractor` variants explicitly, the
variant generator will derive them; documenting them inline is preferred for
research-grade reproducibility.

## Review checklist

Before finishing an attack template change:

1. JSON validates (`python -c "import json; json.load(open('...'))"`)
2. IDs remain unique within the category
3. Payloads and success indicators are present
4. Category and OWASP mapping still match the templates inside the file
5. No real secrets, real customer data, real API keys in any payload
6. If the template introduces a new `technique`, also update `ai-security-knowledge`

## Cross-references

- Mirror Codex skill: `.codex/skills/attack-template-authoring/SKILL.md`
- Domain context: `.cursor/skills/ai-security-knowledge/SKILL.md`
- Repo invariants: `.cursor/skills/project-conventions/SKILL.md`
