"""Register the 千问云 / DashScope provider from a local env var.

Never pass the key on the command line (it lands in shell history).
Never print the key. Safe to reply with the printed UUID and model ids.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx
from sqlalchemy import select

from app.database import async_session, init_db
from app.models.model_provider import (
    PROVIDER_TYPES,
    ModelProvider,
    serialize_api_keys,
)
from scripts.provider_local_ids import (
    QWEN_DASHSCOPE_PROVIDER_ID,
    QWEN_DASHSCOPE_SLOT,
    write_local_provider_id,
)

ENV_KEY = "DASHSCOPE_API_KEY"
PROVIDER_TYPE = "qwen"
PROVIDER_NAME = "qwen-dashscope"
DEFAULT_BASE_URL = PROVIDER_TYPES[PROVIDER_TYPE]
INTERESTING_MARKERS = ("qwen", "deepseek", "kimi", "glm", "minimax", "moonshot")


def _require_api_key() -> str:
    key = (os.environ.get(ENV_KEY) or "").strip()
    if not key:
        raise SystemExit(
            f"{ENV_KEY} is empty. Export it in your own shell; do not paste "
            "the key into chat or pass it as a CLI flag."
        )
    return key


def interesting_model_ids(model_ids: list[str], *, limit: int = 40) -> list[str]:
    interesting = [
        mid
        for mid in model_ids
        if any(marker in mid.lower() for marker in INTERESTING_MARKERS)
    ]
    return interesting[:limit]


async def probe_models(api_key: str, base_url: str) -> list[str]:
    models_url = f"{base_url.rstrip('/')}/models"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            models_url,
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if resp.status_code == 401:
        raise SystemExit("DashScope rejected the key (HTTP 401). Rotate it in the console; do not paste it here.")
    if resp.status_code >= 400:
        raise SystemExit(f"DashScope /models failed: HTTP {resp.status_code}")
    payload = resp.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise SystemExit("DashScope /models returned an unexpected payload")
    ids = [str(item.get("id")) for item in data if isinstance(item, dict) and item.get("id")]
    if not ids:
        raise SystemExit("DashScope /models returned zero chat model ids")
    return ids


async def upsert_provider(*, api_key: str, base_url: str) -> ModelProvider:
    await init_db()
    raw = serialize_api_keys([{"label": "dashscope", "key": api_key}])
    async with async_session() as session:
        existing = await session.get(ModelProvider, QWEN_DASHSCOPE_PROVIDER_ID)
        if existing is None:
            result = await session.execute(
                select(ModelProvider).where(
                    ModelProvider.name == PROVIDER_NAME,
                    ModelProvider.provider_type == PROVIDER_TYPE,
                )
            )
            existing = result.scalar_one_or_none()
        if existing is None:
            provider = ModelProvider(
                id=QWEN_DASHSCOPE_PROVIDER_ID,
                name=PROVIDER_NAME,
                provider_type=PROVIDER_TYPE,
                api_key=raw,
                base_url=base_url,
                enabled=True,
            )
            session.add(provider)
        else:
            provider = existing
            provider.name = PROVIDER_NAME
            provider.provider_type = PROVIDER_TYPE
            provider.api_key = raw
            provider.base_url = base_url
            provider.enabled = True
        await session.commit()
        await session.refresh(provider)
        return provider


def _print_probe(model_ids: list[str]) -> None:
    shown = interesting_model_ids(model_ids)
    print(f"models_total={len(model_ids)}")
    print("interesting_ids:")
    for mid in shown:
        print(f"  {mid}")
    if len(model_ids) > len(shown):
        print(f"  … {len(model_ids) - len(shown)} more not listed")


async def _run(args: argparse.Namespace) -> None:
    api_key = _require_api_key()
    base_url = (os.environ.get("DASHSCOPE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")

    if not args.no_probe:
        model_ids = await probe_models(api_key, base_url)
        _print_probe(model_ids)

    if args.probe_only:
        return

    provider = await upsert_provider(api_key=api_key, base_url=base_url)
    experiments_dir = Path(__file__).resolve().parents[1] / "experiments"
    write_local_provider_id(experiments_dir, QWEN_DASHSCOPE_SLOT, provider.id)
    print(f"slot={QWEN_DASHSCOPE_SLOT}")
    print(f"provider_id={provider.id}")
    print(f"provider_type={provider.provider_type}")
    print(f"base_url={provider.base_url}")
    print("ok: key stored in local DB only. Reply with provider_id + a few model ids, never the key.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe-only",
        action="store_true",
        help="Call /models and print ids; do not write the local database.",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="Skip the live /models call and only upsert the local provider row.",
    )
    args = parser.parse_args(argv)
    if args.probe_only and args.no_probe:
        raise SystemExit("choose one of --probe-only or --no-probe")
    asyncio.run(_run(args))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
