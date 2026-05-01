---
name: project-conventions
description: >-
  Repository-specific architecture, coding conventions, and Codex-native
  workflow expectations for this AI security testing platform. Use when
  working anywhere in this repository and you need guidance on project
  structure, module boundaries, or repo-wide implementation rules.
---

# Project Conventions

Use this skill as the repository-wide baseline when working in this project.

For specialized work, combine it with:

- `$fastapi-patterns` for backend details
- `$react-dashboard` for frontend details
- `$attack-template-authoring` for attack template JSON updates
- `$ai-security-knowledge` for security domain reasoning

## Repository Scope

This project is an AI application security testing platform focused on:

- prompt injection
- system prompt leakage
- sensitive information disclosure
- jailbreak behavior
- application-layer AI security evaluation

## Repository Structure

```text
ai-security/
|-- backend/
|   `-- app/
|       |-- api/
|       |-- attack_templates/
|       |-- core/
|       |-- models/
|       |-- schemas/
|       `-- services/
|-- docs/
|-- frontend/
|   `-- src/
|       |-- api/
|       |-- components/
|       |-- hooks/
|       |-- pages/
|       |-- types/
|       `-- utils/
|-- docker-compose.yml
`-- README.md
```

## Repository-Wide Rules

- Prefer targeted, compatibility-aware changes over broad refactors unless the task requires otherwise.
- Keep backend business logic in `services/`, not in route handlers.
- Keep request and response contracts in `schemas/`.
- Keep frontend API access in `frontend/src/api/`.
- Keep reusable frontend types in `frontend/src/types/`.
- Prefer ASCII in new files unless the file already uses Unicode or the content clearly requires it.

## Security Testing Rules

- Preserve evidence fields when modifying scan, analysis, or report flows.
- Do not weaken traceability just to simplify storage or UI.
- Prefer explicit, inspectable protocol fields over opaque blobs once a contract is stable.

## Codex-Native Workflow Mapping

The old Cursor rules included runtime-specific MCP instructions. For Codex in this repository, use these equivalents:

- Use `update_plan` for multi-step work.
- Use short `commentary` updates while working.
- Ask the user directly and concisely when a decision is required.
- Do not spawn sub-agents unless the user explicitly asks for delegation.

## Before Changing Behavior

Before modifying the scan or report pipeline:

1. identify the persisted data model involved
2. identify the API response shape that depends on it
3. identify which frontend page consumes that shape
4. preserve compatibility unless the task explicitly allows a breaking change
