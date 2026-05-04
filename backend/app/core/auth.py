"""
API key authentication middleware (Stage 1.1a — default-deny).

Behaviour:

* ``settings.auth_required = True`` (default): every API request must
  carry ``X-API-Key: <settings.app_secret>``. Public paths (``/health``,
  ``/docs*``, ``/redoc*``, ``/openapi.json``) and CORS preflight
  (``OPTIONS``) bypass the check.

* ``settings.auth_required = False``: middleware is a no-op (intended
  for local development; ``app_secret`` is ignored).

The companion startup guard ``app.main._validate_auth_config`` ensures
``auth_required=True`` is never paired with an empty ``app_secret``,
preventing a silent open-by-misconfiguration scenario.

WebSocket connections bypass this middleware entirely (Starlette's
``BaseHTTPMiddleware`` only intercepts ``scope["type"] == "http"``).
WS authentication is handled separately by ``app.core.ws_auth``
(Stage 1.1d).
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.auth_required:
            return await call_next(request)

        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not settings.app_secret or api_key != settings.app_secret:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API key"},
            )

        return await call_next(request)
