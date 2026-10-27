"""Seed (or reset) the ``mailbot-agent`` adapter from its JSON fixture.

The adapter wires the Evidence-Ladder platform to the MailBot function-calling
agent so an indirect-prompt-injection scan can light up E4 (tool logs observed
via ``/chat?format=json``) and E5 (business-state probe verified via
``/audit/email-ops``): the agent reads a malicious email body, forwards the
inbox to ``attacker-evil.com``, yet the user-facing reply looks normal —
``concealed_success``.

Usage::

    cd backend && python -m app.scripts.seed_mailbot_adapter
    # the base URL defaults to MOCK_MAILBOT_URL (http://localhost:8003; Docker
    # Compose sets http://mailbot:8003). Point it elsewhere with:
    cd backend && python -m app.scripts.seed_mailbot_adapter --base-url http://10.0.0.5:8003

The Adapters page imports the same definition ("示例适配器") but never touches an
existing adapter; this script resets an existing ``mailbot-agent`` to the
fixture, or creates it.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.database import async_session, init_db
from app.services.sample_adapters import SAMPLE_ADAPTERS, load_adapter_definition, upsert_adapter

SPEC = SAMPLE_ADAPTERS["mailbot"]
DEFAULT_FIXTURE = SPEC.fixture_path


async def seed_adapter(fixture_path: Path, base_url: str | None = None) -> str:
    definition = load_adapter_definition(fixture_path, base_url=base_url or SPEC.configured_base_url())

    await init_db()
    async with async_session() as session:
        adapter, created = await upsert_adapter(session, definition, overwrite=True)
    print(f"mailbot-agent adapter {'created' if created else 'updated'}: id={adapter.id}")
    return adapter.id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed the mailbot-agent adapter.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Override the MailBot base URL (default: MOCK_MAILBOT_URL).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(seed_adapter(args.fixture, base_url=args.base_url))


if __name__ == "__main__":
    main()
