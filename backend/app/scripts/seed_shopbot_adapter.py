"""Seed (or reset) the ``shopbot-agent`` adapter from its JSON fixture.

The adapter wires the Evidence-Ladder platform to the ShopBot function-calling
agent so a privilege-escalation scan can light up E4 (tool logs observed via
``/chat?format=json``) and E5 (business-state probe verified via
``/audit/order-ops``).

Usage::

    cd backend && python -m app.scripts.seed_shopbot_adapter
    # the base URL defaults to MOCK_SHOPBOT_URL (http://localhost:8002; Docker
    # Compose sets http://shopbot:8002). Point it elsewhere with --base-url.

The Adapters page imports the same definition ("示例适配器") but never touches an
existing adapter; this script resets an existing ``shopbot-agent`` to the
fixture, or creates it.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.database import async_session, init_db
from app.services.sample_adapters import SAMPLE_ADAPTERS, load_adapter_definition, upsert_adapter

SPEC = SAMPLE_ADAPTERS["shopbot"]
DEFAULT_FIXTURE = SPEC.fixture_path


async def seed_adapter(fixture_path: Path, base_url: str | None = None) -> str:
    definition = load_adapter_definition(fixture_path, base_url=base_url or SPEC.configured_base_url())

    await init_db()
    async with async_session() as session:
        adapter, created = await upsert_adapter(session, definition, overwrite=True)
    print(f"shopbot-agent adapter {'created' if created else 'updated'}: id={adapter.id}")
    return adapter.id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed the shopbot-agent adapter.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Override the ShopBot base URL (default: MOCK_SHOPBOT_URL).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(seed_adapter(args.fixture, base_url=args.base_url))


if __name__ == "__main__":
    main()
