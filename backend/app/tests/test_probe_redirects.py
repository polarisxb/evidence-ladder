import httpx
import pytest

from app.services import adapter_executor, probe_executor


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("host", ["169.254.169.254", "10.0.0.1", "172.16.0.1", "192.168.0.1"])
@pytest.mark.parametrize("operation", ["probe", "invoke"])
async def test_redirect_never_reaches_private_host(monkeypatch, status, host, operation):
    visited = []

    def respond(request):
        visited.append(str(request.url))
        if len(visited) == 1:
            return httpx.Response(status, headers={"Location": f"http://{host}/private"})
        return httpx.Response(200, text="private data")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(respond),
    ))
    adapter = {
        "name": "redirect-fixture", "mode": "direct_http_adapter", "transport": "http_json",
        "base_url": "https://public.example.com", "auth_config": {"type": "none"},
        "invoke_config": {"method": "GET", "path": "/start"},
        "response_extract": {"mode": "raw_text"},
        "probe_config": {
            "enabled": True, "steps": [{"name": "audit", "method": "GET", "path": "/start"}],
            "assertions": [{"type": "status_code_is", "step": "audit", "status_code": 200}],
        },
    }
    common = dict(runtime_vars=None, scan_id=None, case_id=None, variant_type="attack")
    if operation == "probe":
        result = await probe_executor.execute_probe(adapter, session_id=None, **common)
        succeeded = result.verified
    else:
        result = await adapter_executor.execute_adapter_request(adapter, prompt="fixture", history=None, **common)
        succeeded = result["success"]
    assert visited == ["https://public.example.com/start"]
    assert not succeeded
