import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.auth import AuthMiddleware
from app.core.exceptions import AppException, app_exception_handler
from app.database import init_db
from app.api import api_router
from app.services.llm_scheduler import init_scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    description="AI Application Security Testing Platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)
app.add_exception_handler(AppException, app_exception_handler)
app.include_router(api_router)


@app.on_event("startup")
async def startup():
    await init_db()
    await init_scheduler()


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
