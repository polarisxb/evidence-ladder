import logging
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

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
async def test_connection(target_url: str, api_key: str | None = None):
    """Test connectivity to a target AI API endpoint."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = await client.get(target_url, headers=headers)
            return {
                "data": {"reachable": True, "status_code": resp.status_code},
                "message": "ok",
            }
    except Exception as e:
        return {
            "data": {"reachable": False, "error": str(e)},
            "message": "Connection failed",
        }
