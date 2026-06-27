"""WebSocket authentication helper (Stage 1.1d).

Starlette's ``BaseHTTPMiddleware`` — which we rely on for the
default-deny HTTP auth (``app.core.auth``) — does not apply to
WebSocket connections (it only intercepts ``scope['type'] == 'http'``).
This module closes that gap for ``/api/v1/scans/ws/{task_id}`` by
validating a shared secret against ``settings.app_secret`` before
calling ``websocket.accept()``.

Two token channels are supported, in order of preference:

1. **Sec-WebSocket-Protocol subprotocol** — the client requests a
   subprotocol named ``api-key.<token>``. This is the recommended
   channel because the token is sent as a WS protocol negotiation
   header rather than in the URL (which would otherwise leak into
   access logs, referrer headers, and browser history).
2. **``?token=<token>`` query parameter** — a fallback for simple
   clients (e.g. the current frontend). Servers should treat the
   token as a short-lived secret regardless of channel.

When ``settings.auth_required`` is False the helper accepts the
connection without checking (parity with the HTTP middleware's opt-out).

On success the helper performs ``websocket.accept()`` (with the
matched subprotocol, if any). On failure it calls
``websocket.close(code=1008)`` — 1008 is the WS Policy Violation close
code — and returns False so the caller can early-return.
"""
from __future__ import annotations

import hmac

from starlette.websockets import WebSocket

from app.config import settings


_SUBPROTOCOL_PREFIX = "api-key."


async def require_ws_token(websocket: WebSocket) -> bool:
    """Validate WS auth and complete/deny the handshake.

    On success the websocket is already ``accept``-ed (with the chosen
    subprotocol when applicable); callers must NOT call ``accept()``
    again. On failure the websocket is already ``close``-d with code
    1008; callers must early-return.
    """
    if not settings.auth_required:
        await websocket.accept()
        return True

    expected = settings.app_secret or ""

    # 1. Subprotocol channel (preferred).
    subprotocols = list(websocket.scope.get("subprotocols") or [])
    for proto in subprotocols:
        if not isinstance(proto, str) or not proto.startswith(_SUBPROTOCOL_PREFIX):
            continue
        candidate = proto[len(_SUBPROTOCOL_PREFIX):]
        if expected and _secret_matches(candidate, expected):
            # Confirm the negotiated subprotocol so the client's
            # Sec-WebSocket-Protocol handshake step completes cleanly.
            await websocket.accept(subprotocol=proto)
            return True

    # 2. Query-parameter channel (fallback).
    token = websocket.query_params.get("token", "") or ""
    if expected and _secret_matches(token, expected):
        await websocket.accept()
        return True

    # No valid credential found.
    await websocket.close(code=1008)
    return False


def _secret_matches(candidate: str, expected: str) -> bool:
    """Constant-time comparison of a client-supplied token against the secret."""
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))
