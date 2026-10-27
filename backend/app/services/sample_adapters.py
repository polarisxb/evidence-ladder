"""Built-in sample adapters for the bundled agent mock targets.

MailBot and ShopBot are function-calling agents. Wired as adapters they expose
tool logs (E4) through ``/chat?format=json`` and business state (E5) through
their ``/audit`` endpoints, which a plain ``custom`` target cannot reach. The
adapter definitions ship as JSON fixtures; each fixture's ``base_url`` is
replaced with the configured mock-target address so one definition works both
under Docker Compose and on localhost.

Used by the ``/adapters/samples`` API (import from the Adapters page or a New
Scan preset) and by the ``seed_*_adapter`` CLI scripts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AppException
from app.models import Adapter
from app.schemas.adapter import AdapterCreate

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@dataclass(frozen=True)
class SampleAdapterSpec:
    key: str
    fixture: str
    base_url_setting: str

    @property
    def fixture_path(self) -> Path:
        return FIXTURES_DIR / self.fixture

    def configured_base_url(self) -> str:
        return str(getattr(settings, self.base_url_setting))


SAMPLE_ADAPTERS: dict[str, SampleAdapterSpec] = {
    "mailbot": SampleAdapterSpec("mailbot", "mailbot_agent_adapter.json", "mock_mailbot_url"),
    "shopbot": SampleAdapterSpec("shopbot", "shopbot_agent_adapter.json", "mock_shopbot_url"),
}


def get_sample_spec(key: str) -> SampleAdapterSpec:
    spec = SAMPLE_ADAPTERS.get(key)
    if spec is None:
        raise AppException(404, f"Unknown sample adapter: {key}")
    return spec


def load_adapter_definition(fixture_path: Path, base_url: str | None = None) -> AdapterCreate:
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    if base_url:
        raw["base_url"] = base_url.rstrip("/")
    return AdapterCreate.model_validate(raw)


def sample_definition(spec: SampleAdapterSpec, base_url: str | None = None) -> AdapterCreate:
    """The spec's fixture, pointed at ``base_url`` or the configured mock-target URL."""
    return load_adapter_definition(spec.fixture_path, base_url=base_url or spec.configured_base_url())


def adapter_payload(body: AdapterCreate) -> dict:
    data = body.model_dump(exclude_none=True)
    for key in ("auth_config", "session_config", "invoke_config", "response_extract", "probe_config"):
        value = getattr(body, key, None)
        if value is not None and hasattr(value, "model_dump"):
            data[key] = value.model_dump(exclude_none=True)
    return data


async def find_adapter_by_name(db: AsyncSession, name: str) -> Adapter | None:
    # Names are not unique; the oldest row is the one a previous import created.
    result = await db.execute(select(Adapter).where(Adapter.name == name).order_by(Adapter.created_at))
    return result.scalars().first()


async def upsert_adapter(
    db: AsyncSession, definition: AdapterCreate, *, overwrite: bool
) -> tuple[Adapter, bool]:
    """Create the adapter, or reuse the existing one with the same name.

    ``overwrite`` resets an existing row to the definition (the CLI seed
    behaviour); without it an existing row, including any edits the user made,
    is returned untouched. Returns ``(adapter, created)``.
    """
    payload = adapter_payload(definition)
    adapter = await find_adapter_by_name(db, definition.name)
    created = adapter is None
    if created:
        adapter = Adapter(**payload)
        db.add(adapter)
    elif overwrite:
        for key, value in payload.items():
            setattr(adapter, key, value)
    await db.commit()
    await db.refresh(adapter)
    return adapter, created
