"""Shared canary token extraction and matching utilities.

Used by verdict_engine and control_variants to avoid duplicating
the same regex patterns and matching logic.
"""

from __future__ import annotations

import re

CANARY_RE = re.compile(r"\b(?:CANARY|MARKER|HONEY)[A-Z0-9_-]{4,}\b", re.IGNORECASE)


def collect_canary_tokens(target_config: dict | None) -> list[str]:
    """Extract all canary tokens from target_config (explicit list + auto-detected from system_prompt)."""
    system_prompt = (target_config or {}).get("system_prompt", "") or ""
    configured = list((target_config or {}).get("canary_tokens", []) or [])
    configured.extend(match.group(0) for match in CANARY_RE.finditer(system_prompt))
    return sorted({token for token in configured if isinstance(token, str) and token.strip()})


def extract_canary_tokens_from_text(text: str) -> list[str]:
    """Auto-detect canary-style tokens in arbitrary text."""
    return sorted({match.group(0) for match in CANARY_RE.finditer(text)})


def find_canary_matches(text: str, tokens: list[str]) -> list[str]:
    """Return which of the given canary tokens appear in text (word-boundary match)."""
    lowered = text.lower()
    matched = []
    for token in tokens:
        if not token:
            continue
        pattern = r'\b' + re.escape(token.lower()) + r'\b'
        if re.search(pattern, lowered):
            matched.append(token)
    return matched


def contains_canary(text: str, tokens: list[str]) -> bool:
    """Return True if any canary token appears in text."""
    return len(find_canary_matches(text, tokens)) > 0
