import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _stage1_test_security_defaults(monkeypatch: pytest.MonkeyPatch):
    """Stage 1.1a/1.1b test-mode defaults.

    The repo flips to default-deny auth and a strict SSRF guard. To keep
    the existing 35+ tests passing without touching every file, we relax
    those two flags for tests by default. Individual tests that exercise
    the new behaviour use ``monkeypatch.setattr`` again to re-enable.
    """
    from app.config import settings

    # Only apply when the new fields exist (tolerant during the Stage 1.1a
    # transition where AuthMiddleware/url_guard land in separate commits).
    if hasattr(settings, "auth_required"):
        monkeypatch.setattr("app.config.settings.auth_required", False)
    if hasattr(settings, "allow_localhost_targets"):
        monkeypatch.setattr("app.config.settings.allow_localhost_targets", True)
