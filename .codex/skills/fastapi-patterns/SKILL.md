---
name: fastapi-patterns
description: >-
  FastAPI backend development patterns for this AI security testing platform.
  Use when creating or modifying backend API endpoints, services, async data
  access, or database models in this repository.
---

# FastAPI Backend Patterns

Use this together with:

- `$project-conventions` for repository-wide structure and compatibility rules
- `$attack-template-authoring` when editing `backend/app/attack_templates/**/*.json`
- `$openai-integration` when changing LLM analyzer or generation flows

## Repository Structure

```text
backend/
|-- app/
|   |-- main.py
|   |-- config.py
|   |-- database.py
|   |-- models/
|   |-- schemas/
|   |-- api/
|   |-- services/
|   |-- core/
|   `-- attack_templates/
|-- tests/
|-- requirements.txt
`-- Dockerfile
```

## Backend Rules

- Prefer async end-to-end for database, HTTP, and other I/O operations.
- Use Pydantic v2 models for request and response validation.
- Raise `AppException` from services and shared logic; keep `HTTPException` at route boundaries only.
- Use Python type hints for parameters and return values.
- Prefer SQLAlchemy 2.0 style APIs.
- Keep sensitive configuration in `.env` / settings rather than source files.

## Layering

- `api/`: route handlers and transport concerns only
- `services/`: business logic and orchestration
- `schemas/`: request and response contracts
- `models/`: ORM persistence models
- `core/`: shared utilities, exceptions, and framework helpers

Do not push business logic into route handlers if it can live in `services/`.

## Common Patterns

### Async Database Access

```python
async def get_scan(db: AsyncSession, scan_id: str) -> ScanTask | None:
    result = await db.execute(select(ScanTask).where(ScanTask.id == scan_id))
    return result.scalar_one_or_none()
```

### Route + Service Split

```python
@router.get("/{task_id}")
async def get_scan(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await load_scan(task_id, db)
    return {"data": ScanResponse.model_validate(task), "message": "ok"}
```

### AppException Usage

```python
if not task:
    raise AppException(404, "Scan task not found")
```

## When Changing Persistence

This repository currently initializes tables via `Base.metadata.create_all()`.
Prefer additive schema changes in-place.

When you add a new persisted concept:

1. add the model
2. add the schema
3. add the API serializer
4. identify which frontend page reads it

Avoid assuming a full migration framework exists unless you introduce one explicitly.
