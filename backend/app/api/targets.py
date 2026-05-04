import logging
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.url_guard import validate_target_url
from app.services.vulnerable_ai import VULNERABLE_LEVELS, chat_with_vulnerable_ai

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    level: int = Field(1, ge=1, le=4)
    history: list[ChatMessage] = Field(default_factory=list)


class TestConnectionRequest(BaseModel):
    """Stage 1.1c — credentials must ride in the JSON body, never as
    query parameters (which end up in server/proxy access logs)."""
    target_url: str
    api_key: str | None = None


@router.get("/builtin", response_model=dict)
async def list_builtin_targets():
    """List all built-in vulnerable AI targets with their protection levels."""
    targets = []
    for level, info in VULNERABLE_LEVELS.items():
        targets.append({
            "level": level,
            "name": info["name"],
            "description": info["description"],
            "protection": info["protection"],
        })
    return {"data": targets, "message": "ok"}


@router.post("/chat", response_model=dict)
async def chat_with_target(body: ChatRequest):
    """Send a message to the built-in vulnerable AI and get a response."""
    history = [{"role": m.role, "content": m.content} for m in body.history]
    response = await chat_with_vulnerable_ai(
        message=body.message,
        level=body.level,
        conversation_history=history,
    )
    return {"data": {"response": response}, "message": "ok"}


@router.post("/test-connection", response_model=dict)
async def test_connection(body: TestConnectionRequest):
    """Test connectivity to a target AI API endpoint.

    Stage 1.1c: credentials are accepted in the JSON body only. Any
    error surface is passed through ``sanitize_error`` so ``sk-*``,
    ``key-*`` and ``Bearer *`` tokens cannot bleed back to the caller.
    The request's own ``api_key`` is never included in the response.
    """
    import httpx

    from app.services.error_utils import sanitize_error

    # Stage 1.1b — refuse SSRF before any outbound request is made.
    validate_target_url(body.target_url)

    try:
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=False
        ) as client:
            headers = {}
            if body.api_key:
                headers["Authorization"] = f"Bearer {body.api_key}"
            resp = await client.get(body.target_url, headers=headers)
            return {
                "data": {"reachable": True, "status_code": resp.status_code},
                "message": "ok",
            }
    except Exception as e:
        return {
            "data": {"reachable": False, "error": sanitize_error(e)},
            "message": "Connection failed",
        }
