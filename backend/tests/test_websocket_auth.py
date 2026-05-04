"""Stage 1.1d: WebSocket authentication at ``/api/v1/scans/ws/{task_id}``.

The HTTP AuthMiddleware (Stage 1.1a) does not apply to websockets —
Starlette's ``BaseHTTPMiddleware`` only intercepts ``scope['type'] ==
'http'``. These tests pin the contract that:

* when ``settings.auth_required`` is True, the WS endpoint MUST refuse
  unauthenticated / wrongly-authenticated connections with close code
  1008 (Policy Violation) **before** ``accept()``.
* the endpoint accepts two token channels, in order of preference:
    1. ``Sec-WebSocket-Protocol: api-key.<token>`` subprotocol
       (preferred: tokens never end up in URLs/access logs).
    2. ``?token=<token>`` query parameter (fallback for simple clients).
* when ``settings.auth_required`` is False, parity with HTTP is
  preserved — no token required.

Uses FastAPI's TestClient (sync) because ``httpx.AsyncClient`` via
ASGITransport does not expose WebSocket primitives.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


class TestWsAuthEnabled:
    def test_unauthenticated_ws_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=True + no token → close 1008 before accept."""
        monkeypatch.setattr("app.config.settings.auth_required", True)
        monkeypatch.setattr(
            "app.config.settings.app_secret", "test-secret-xyz"
        )
        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/api/v1/scans/ws/any-task-id"
            ):
                pass
        assert exc_info.value.code == 1008

    def test_authenticated_ws_accepted_via_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=True + ?token=<correct> → connection accepted."""
        monkeypatch.setattr("app.config.settings.auth_required", True)
        monkeypatch.setattr(
            "app.config.settings.app_secret", "test-secret-xyz"
        )
        client = TestClient(app)
        with client.websocket_connect(
            "/api/v1/scans/ws/any-task-id?token=test-secret-xyz"
        ) as ws:
            # Connection accepted; close cleanly to avoid dangling _ws_clients.
            ws.close()

    def test_authenticated_ws_accepted_via_subprotocol(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=True + subprotocol api-key.<correct> → accepted."""
        monkeypatch.setattr("app.config.settings.auth_required", True)
        monkeypatch.setattr(
            "app.config.settings.app_secret", "test-secret-xyz"
        )
        client = TestClient(app)
        with client.websocket_connect(
            "/api/v1/scans/ws/any-task-id",
            subprotocols=["api-key.test-secret-xyz"],
        ) as ws:
            ws.close()

    def test_invalid_token_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=True + wrong ?token → close 1008."""
        monkeypatch.setattr("app.config.settings.auth_required", True)
        monkeypatch.setattr(
            "app.config.settings.app_secret", "test-secret-xyz"
        )
        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/api/v1/scans/ws/any-task-id?token=wrong-key"
            ):
                pass
        assert exc_info.value.code == 1008


class TestWsAuthDisabled:
    def test_ws_open_when_auth_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=False → ws accept with no token (parity with HTTP)."""
        monkeypatch.setattr("app.config.settings.auth_required", False)
        client = TestClient(app)
        with client.websocket_connect(
            "/api/v1/scans/ws/any-task-id"
        ) as ws:
            ws.close()
