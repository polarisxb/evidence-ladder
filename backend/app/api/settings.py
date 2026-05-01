import logging
import os

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings
from app.core.openai_client import get_platform_openai_client

logger = logging.getLogger(__name__)
router = APIRouter()

ENV_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")


class SettingsResponse(BaseModel):
    openai_api_key_set: bool
    openai_base_url: str | None
    openai_model: str
    openai_mini_model: str
    database_url: str
    cors_origins: list[str]
    allow_localhost_targets: bool
    debug: bool


class SettingsUpdate(BaseModel):
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    openai_mini_model: str | None = None
    debug: bool | None = None


@router.get("", response_model=dict)
async def get_settings():
    return {
        "data": SettingsResponse(
            openai_api_key_set=bool(settings.openai_api_key),
            openai_base_url=settings.openai_base_url,
            openai_model=settings.openai_model,
            openai_mini_model=settings.openai_mini_model,
            database_url=settings.database_url.split("///")[-1],
            cors_origins=settings.cors_origins,
            allow_localhost_targets=settings.allow_localhost_targets,
            debug=settings.debug,
        ).model_dump(),
        "message": "ok",
    }


@router.put("", response_model=dict)
async def update_settings(body: SettingsUpdate):
    updated = []

    if body.openai_api_key is not None:
        settings.openai_api_key = body.openai_api_key
        _update_env_file("OPENAI_API_KEY", body.openai_api_key)
        updated.append("openai_api_key")

    if body.openai_base_url is not None:
        settings.openai_base_url = body.openai_base_url or None
        _update_env_file("OPENAI_BASE_URL", body.openai_base_url or "")
        updated.append("openai_base_url")

    if body.openai_model is not None:
        settings.openai_model = body.openai_model
        _update_env_file("OPENAI_MODEL", body.openai_model)
        updated.append("openai_model")

    if body.openai_mini_model is not None:
        settings.openai_mini_model = body.openai_mini_model
        _update_env_file("OPENAI_MINI_MODEL", body.openai_mini_model)
        updated.append("openai_mini_model")

    if body.debug is not None:
        settings.debug = body.debug
        _update_env_file("DEBUG", str(body.debug).lower())
        updated.append("debug")

    if any(
        k in updated
        for k in ("openai_api_key", "openai_base_url", "openai_model", "openai_mini_model")
    ):
        from app.services.ai_analyzer import reset_analyzer_client

        reset_analyzer_client()

    logger.info("Settings updated: %s", updated)
    return {"data": {"updated": updated}, "message": "Settings saved"}


@router.post("/test-openai", response_model=dict)
async def test_openai_connection():
    if not settings.openai_api_key:
        return {"data": {"connected": False, "error": "No API key configured"}, "message": "error"}

    try:
        client = get_platform_openai_client()
        response = await client.chat.completions.create(
            model=settings.openai_mini_model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        model_used = response.model
        return {
            "data": {"connected": True, "model": model_used},
            "message": "ok",
        }
    except Exception as e:
        return {
            "data": {"connected": False, "error": str(e)},
            "message": "Connection failed",
        }


@router.get("/system-status", response_model=dict)
async def get_system_status():
    import platform
    import sys

    from app.database import async_session
    from sqlalchemy import text

    db_ok = False
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass

    openai_ok = bool(settings.openai_api_key)

    return {
        "data": {
            "python_version": sys.version.split()[0],
            "platform": platform.system(),
            "database_connected": db_ok,
            "openai_configured": openai_ok,
            "app_name": settings.app_name,
            "debug_mode": settings.debug,
        },
        "message": "ok",
    }


def _update_env_file(key: str, value: str):
    lines = []
    found = False

    if os.path.exists(ENV_FILE_PATH):
        with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}\n")

    with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
