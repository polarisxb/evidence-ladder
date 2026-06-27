import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def _ensure_db_schema():
    """Create the SQLite schema before the API integration tests run.

    The ``tests/`` API suite drives the app via ``ASGITransport(app=app)``,
    which never triggers the FastAPI lifespan where ``init_db()`` runs. The
    tests previously passed only because a pre-populated ``ai_security.db`` was
    committed to the repo; once that artifact is no longer tracked, a clean
    checkout (e.g. CI) starts with an empty database and every query raises
    ``no such table``. Build the schema here with a synchronous engine on the
    same database file, reusing the additive-column migrations from
    ``init_db`` so the schema matches production exactly.
    """
    import app.main  # noqa: F401  ensure all ORM models are imported -> metadata
    from sqlalchemy import create_engine

    from app.config import settings
    from app.database import (
        Base,
        _ensure_additive_adapter_columns,
        _ensure_additive_attack_case_columns,
        _ensure_additive_scan_task_columns,
    )

    sync_engine = create_engine(settings.database_url.replace("+aiosqlite", ""))
    try:
        with sync_engine.begin() as conn:
            Base.metadata.create_all(conn)
            _ensure_additive_scan_task_columns(conn)
            _ensure_additive_adapter_columns(conn)
            _ensure_additive_attack_case_columns(conn)
    finally:
        sync_engine.dispose()


@pytest.fixture(autouse=True)
def _stage1_test_security_defaults(monkeypatch: pytest.MonkeyPatch):
    """Stage 1.1a/1.1b test-mode defaults.

    The repo flips to default-deny auth and a strict SSRF guard. To keep
    the existing 35+ tests passing without touching every file, we relax
    auth and pin the SSRF flags to their secure defaults for tests.
    Individual tests that exercise the new behaviour use
    ``monkeypatch.setattr`` again to re-enable.

    ``allow_private_targets`` is pinned to ``False`` here so the url_guard
    unit tests stay hermetic regardless of the ambient environment (CI
    sets ``ALLOW_PRIVATE_TARGETS=true`` for the app integration suite,
    which would otherwise leak in and break the default-deny assertions).
    """
    from app.config import settings

    # Only apply when the new fields exist (tolerant during the Stage 1.1a
    # transition where AuthMiddleware/url_guard land in separate commits).
    if hasattr(settings, "auth_required"):
        monkeypatch.setattr("app.config.settings.auth_required", False)
    if hasattr(settings, "allow_localhost_targets"):
        monkeypatch.setattr("app.config.settings.allow_localhost_targets", True)
    if hasattr(settings, "allow_private_targets"):
        monkeypatch.setattr("app.config.settings.allow_private_targets", False)
