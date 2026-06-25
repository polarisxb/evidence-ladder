"""Seed (or update) the ``shopbot-agent`` adapter from its JSON fixture.

The adapter wires the Evidence-Ladder platform to the ShopBot function-calling
agent so a privilege-escalation scan can light up E4 (tool logs observed via
``/chat?format=json``) and E5 (business-state probe verified via
``/audit/order-ops``).

Usage::

    cd backend && python -m app.scripts.seed_shopbot_adapter

The operation is idempotent: an existing adapter with the same ``name`` is
updated in place; otherwise a new row is created.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.database import async_session, init_db
from app.models import Adapter
from app.schemas.adapter import AdapterCreate

DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "shopbot_agent_adapter.json"


def _adapter_payload(body: AdapterCreate) -> dict:
    data = body.model_dump(exclude_none=True)
    for key in ("auth_config", "session_config", "invoke_config", "response_extract", "probe_config"):
        value = getattr(body, key, None)
        if value is not None and hasattr(value, "model_dump"):
            data[key] = value.model_dump(exclude_none=True)
    return data


def load_adapter_definition(fixture_path: Path) -> AdapterCreate:
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    return AdapterCreate.model_validate(raw)


async def seed_adapter(fixture_path: Path) -> str:
    definition = load_adapter_definition(fixture_path)
    payload = _adapter_payload(definition)

    await init_db()
    async with async_session() as session:
        existing = (
            await session.execute(select(Adapter).where(Adapter.name == definition.name))
        ).scalar_one_or_none()

        if existing is None:
            adapter = Adapter(**payload)
            session.add(adapter)
            action = "created"
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
            adapter = existing
            action = "updated"

        await session.commit()
        await session.refresh(adapter)
        print(f"shopbot-agent adapter {action}: id={adapter.id}")
        return adapter.id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed the shopbot-agent adapter.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(seed_adapter(args.fixture))


if __name__ == "__main__":
    main()
