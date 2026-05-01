---
name: fastapi-patterns
description: >-
  FastAPI backend development patterns for this AI security testing platform.
  Covers project structure, async patterns, WebSocket for real-time updates,
  background tasks, and API design. Use when creating or modifying backend
  API endpoints, services, or database models.
---

# FastAPI Backend Patterns

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py             # Settings via pydantic-settings
│   ├── database.py           # SQLite + SQLAlchemy async setup
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── scan_task.py
│   │   ├── attack_result.py
│   │   └── security_report.py
│   ├── schemas/              # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── scan.py
│   │   └── report.py
│   ├── api/                  # Route handlers
│   │   ├── __init__.py
│   │   ├── scans.py
│   │   ├── reports.py
│   │   ├── targets.py
│   │   └── templates.py
│   ├── services/             # Business logic
│   │   ├── __init__.py
│   │   ├── attack_engine.py
│   │   ├── ai_analyzer.py
│   │   ├── risk_scorer.py
│   │   └── report_generator.py
│   ├── core/                 # Core utilities
│   │   ├── __init__.py
│   │   ├── security.py
│   │   └── exceptions.py
│   └── attack_templates/     # Attack payload data
│       ├── prompt_injection.json
│       ├── system_prompt_extraction.json
│       ├── jailbreak.json
│       └── information_disclosure.json
├── tests/
├── requirements.txt
└── Dockerfile
```

## Key Patterns

### CORS and Middleware

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Logging Setup

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
```

### Config with pydantic-settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "TianJian Libra"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    cors_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"

settings = Settings()
```

### Async SQLAlchemy with SQLite

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase

engine = create_async_engine(settings.database_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session
```

### Background Task for Scans

Scans run as background tasks. Use FastAPI's BackgroundTasks or an async task queue:

```python
from fastapi import BackgroundTasks

@router.post("/scans")
async def create_scan(config: ScanConfig, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    task = ScanTask(status="pending", config=config.model_dump())
    db.add(task)
    await db.commit()
    background_tasks.add_task(run_scan, task.id)
    return {"task_id": task.id, "status": "pending"}
```

### WebSocket for Real-Time Progress

```python
from fastapi import WebSocket
import asyncio

connected_clients: dict[str, list[WebSocket]] = {}

@router.websocket("/ws/scans/{task_id}")
async def scan_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()
    connected_clients.setdefault(task_id, []).append(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        connected_clients[task_id].remove(websocket)

async def broadcast_progress(task_id: str, data: dict):
    for ws in connected_clients.get(task_id, []):
        await ws.send_json(data)
```

### Error Handling

```python
from fastapi import HTTPException

class AppException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
```

### API Response Convention

All API responses follow this structure:

```python
# Success
{"data": {...}, "message": "ok"}

# List with pagination
{"data": [...], "total": 100, "page": 1, "page_size": 20}

# Error
{"error": "description", "detail": "..."}
```

## Dependencies

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy[asyncio]>=2.0.0
aiosqlite>=0.20.0
pydantic-settings>=2.0.0
openai>=1.50.0
httpx>=0.27.0
python-dotenv>=1.0.0
```
