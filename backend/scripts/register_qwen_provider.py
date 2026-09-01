"""Register the 千问云 / DashScope provider from a local env var.

Never pass the key on the command line (it lands in shell history).
Never print the key. Safe to reply with the printed UUID and model ids.

``--probe-only`` uses the stdlib only, so a bare ``python3`` works.
Writing the local DB still needs ``pip install -r requirements.txt``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV_KEY = "DASHSCOPE_API_KEY"
PROVIDER_TYPE = "qwen"
PROVIDER_NAME = "qwen-dashscope"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
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


def parse_models_payload(payload: object) -> list[str]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise SystemExit("DashScope /models returned an unexpected payload")
    ids = [str(item.get("id")) for item in data if isinstance(item, dict) and item.get("id")]
    if not ids:
        raise SystemExit("DashScope /models returned zero chat model ids")
    return ids


def probe_models(api_key: str, base_url: str) -> list[str]:
    models_url = f"{base_url.rstrip('/')}/models"
    request = urllib.request.Request(
        models_url,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            status = getattr(resp, "status", 200)
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise SystemExit(
                "DashScope rejected the key (HTTP 401). Rotate it in the console; "
                "do not paste it here."
            ) from exc
        raise SystemExit(f"DashScope /models failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"DashScope /models network error: {exc.reason}") from exc
    if status >= 400:
        raise SystemExit(f"DashScope /models failed: HTTP {status}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit("DashScope /models returned non-JSON") from exc
    return parse_models_payload(payload)


def _print_probe(model_ids: list[str]) -> None:
    shown = interesting_model_ids(model_ids)
    print(f"models_total={len(model_ids)}")
    print("interesting_ids:")
    for mid in shown:
        print(f"  {mid}")
    if len(model_ids) > len(shown):
        print(f"  … {len(model_ids) - len(shown)} more not listed")


async def upsert_provider(*, api_key: str, base_url: str):
    from sqlalchemy import select

    from app.database import async_session, init_db
    from app.models.model_provider import ModelProvider, serialize_api_keys
    from scripts.provider_local_ids import QWEN_DASHSCOPE_PROVIDER_ID

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


def _run(args: argparse.Namespace) -> None:
    api_key = _require_api_key()
    base_url = (os.environ.get("DASHSCOPE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")

    if not args.no_probe:
        _print_probe(probe_models(api_key, base_url))

    if args.probe_only:
        return

    import asyncio

    from scripts.provider_local_ids import QWEN_DASHSCOPE_SLOT, write_local_provider_id

    provider = asyncio.run(upsert_provider(api_key=api_key, base_url=base_url))
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
    _run(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
