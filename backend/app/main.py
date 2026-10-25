import logging
from contextlib import asynccontextmanager
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import URL

from app.config import settings
from app.core.auth import AuthMiddleware
from app.core.exceptions import AppException, app_exception_handler
from app.database import init_db
from app.api import api_router
from app.services.llm_scheduler import init_scheduler
from app.version import APP_FULL_NAME, APP_VERSION


def _redact_httpx_request_urls(record: logging.LogRecord) -> bool:
    """Keep HTTP diagnostics without logging arbitrary adapter query secrets."""
    if isinstance(record.args, tuple):
        record.args = tuple(
            arg.copy_with(query=urlencode([
                (name, "[REDACTED]") for name, _ in arg.params.multi_items()
            ]).encode("ascii"))
            if isinstance(arg, URL) and arg.query else arg
            for arg in record.args
        )
    return True


logging.getLogger("httpx").addFilter(_redact_httpx_request_urls)
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _validate_auth_config()
    await init_db()
    await init_scheduler()
    yield


app = FastAPI(
    title=f"{APP_FULL_NAME}（{settings.app_name}）",
    description="多源证据分层（E0–E5）与冲突驱动补测的大模型应用黑盒安全评测 API",
    version=APP_VERSION,
    lifespan=lifespan,
)

# Middleware ordering note: Starlette runs the LAST-added middleware as the
# OUTERMOST layer. CORS is added after AuthMiddleware so it wraps it, ensuring
# rejected (e.g. 401) responses still carry CORS headers and the browser can
# read the real status instead of a generic CORS error.
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppException, app_exception_handler)
app.include_router(api_router)


def _validate_auth_config() -> None:
    """Stage 1.1a — fail-fast guard for default-deny auth misconfiguration.

    When ``settings.auth_required`` is True the platform must have a
    non-empty ``settings.app_secret``; otherwise every authenticated
    request would be rejected (DoS-style misconfiguration) — but more
    importantly, an empty secret combined with a defensive comparison
    ``api_key != settings.app_secret`` could mask future regressions.
    Refusing to start surfaces the misconfiguration immediately.
    """
    if settings.auth_required and not settings.app_secret:
        raise RuntimeError(
            "APP_SECRET is required when AUTH_REQUIRED=true. "
            "Set APP_SECRET in .env (e.g. "
            "`python -c \"import secrets; print(secrets.token_urlsafe(32))\"` "
            "to generate one), or set AUTH_REQUIRED=false for local "
            "development."
        )


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "version": APP_VERSION}
