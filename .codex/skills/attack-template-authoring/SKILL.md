---
name: attack-template-authoring
description: >-
  Repository-specific rules for authoring and updating attack template JSON
  files under backend/app/attack_templates. Use when creating, editing, or
  reviewing attack template categories, IDs, payloads, or success indicators.
---

# Attack Template Authoring

Use this skill when editing files under `backend/app/attack_templates/**/*.json`.

For attack semantics and category knowledge, also use:

- `$ai-security-knowledge`

## Template File Shape

Each attack template JSON file should follow this top-level structure:

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

## ID Naming Rules

- Prompt Injection: `PI-001` to `PI-999`
- System Prompt Extraction: `SP-001` to `SP-999`
- Jailbreak: `JB-001` to `JB-999`
- Information Disclosure: `ID-001` to `ID-999`
- Multi-Turn: `MT-001` to `MT-999`

## Required Fields Per Template

- `id`
- `name`
- `technique`
- `severity`
- `payloads`
- `success_indicators`

Minimum expectations:

- every template has at least one payload
- every template has at least one success indicator
- `severity` is one of `critical`, `high`, `medium`, or `low`

## Authoring Rules

- Keep payload text realistic for black-box testing.
- Keep `technique` names stable and machine-friendly.
- Use `multi_turn: true` only when the template genuinely requires ordered turns.
- Keep category metadata aligned with the actual contents of the file.

## Review Checklist

Before finishing an attack template change:

1. verify the JSON is valid
2. verify IDs remain unique within the category
3. verify payloads and success indicators are present
4. verify the category and OWASP mapping still match the templates inside the file
