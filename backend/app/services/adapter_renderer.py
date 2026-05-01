import json
import re
from collections.abc import Mapping
from typing import Any

from app.core.exceptions import AppException

PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][\w\.]*)\s*}}")
PROBE_STEP_TEMPLATE_RE = re.compile(
    r"^probe\.steps\.[A-Za-z_][\w-]*\.(status_code|text|captures\.[A-Za-z_][\w-]*)$"
)

ALLOWED_TEMPLATE_EXACT_PATHS = {
    "session.id",
    "input.prompt",
    "input.history",
    "scan.id",
    "case.id",
    "variant.type",
}
ALLOWED_TEMPLATE_PREFIXES = ("runtime.",)
PROBE_TEMPLATE_EXACT_PATHS = {
    "session.id",
    "scan.id",
    "case.id",
    "variant.type",
}
PROBE_TEMPLATE_PREFIXES = ("runtime.",)


def is_allowed_template_path(path: str, *, allow_probe_context: bool = False) -> bool:
    normalized = path.strip()
    exact_paths = PROBE_TEMPLATE_EXACT_PATHS if allow_probe_context else ALLOWED_TEMPLATE_EXACT_PATHS
    prefixes = PROBE_TEMPLATE_PREFIXES if allow_probe_context else ALLOWED_TEMPLATE_PREFIXES
    if normalized in exact_paths:
        return True
    if any(normalized.startswith(prefix) for prefix in prefixes):
        return True
    if allow_probe_context and PROBE_STEP_TEMPLATE_RE.match(normalized):
        return True
    return False


def iter_template_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, str):
        paths.extend(match.group(1) for match in PLACEHOLDER_RE.finditer(value))
    elif isinstance(value, list):
        for item in value:
            paths.extend(iter_template_paths(item))
    elif isinstance(value, Mapping):
        for item in value.values():
            paths.extend(iter_template_paths(item))
    return paths


def validate_template_tree(value: Any, *, field_name: str, allow_probe_context: bool = False) -> None:
    invalid_paths = sorted(
        {
            path
            for path in iter_template_paths(value)
            if not is_allowed_template_path(path, allow_probe_context=allow_probe_context)
        }
    )
    if invalid_paths:
        joined = ", ".join(invalid_paths)
        raise AppException(400, f"Unsupported template variable(s) in {field_name}: {joined}")


def build_adapter_context(
    *,
    runtime_vars: dict | None,
    prompt: str,
    history: list[dict] | None,
    scan_id: str | None,
    case_id: str | None,
    variant_type: str | None,
    session_id: str | None,
    probe_steps: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "runtime": runtime_vars or {},
        "session": {"id": session_id},
        "input": {
            "prompt": prompt,
            "history": history or [],
        },
        "scan": {"id": scan_id},
        "case": {"id": case_id},
        "variant": {"type": variant_type},
        "probe": {"steps": probe_steps or {}},
    }


def _resolve_path(context: Mapping[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
        else:
            current = None
        if current is None:
            return None
    return current


def _stringify_embedded_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def render_template_tree(value: Any, context: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        exact_match = PLACEHOLDER_RE.fullmatch(value.strip())
        if exact_match:
            return _resolve_path(context, exact_match.group(1))

        return PLACEHOLDER_RE.sub(
            lambda match: _stringify_embedded_value(_resolve_path(context, match.group(1))),
            value,
        )

    if isinstance(value, list):
        return [render_template_tree(item, context) for item in value]

    if isinstance(value, Mapping):
        return {
            str(key): render_template_tree(item, context)
            for key, item in value.items()
        }

    return value
