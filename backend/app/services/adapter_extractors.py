import json
import re
from typing import Any


_PATH_TOKEN_RE = re.compile(r"\.([A-Za-z_][\w-]*)|\[(\d+)\]")


def default_response_extract_for_transport(transport: str) -> dict[str, Any]:
    if transport == "openai_chat":
        return {
            "mode": "json_paths",
            "text_path": "$.choices[0].message.content",
            "error_path": "$.error.message",
            "tool_calls_path": "$.choices[0].message.tool_calls",
        }
    return {
        "mode": "json_paths",
        "text_path": "$.text",
        "error_path": "$.error.message",
        "tool_calls_path": None,
    }


def extract_json_path_value(data: Any, path: str | None) -> Any:
    if not path:
        return None
    normalized = path.strip()
    if normalized == "$":
        return data
    if not normalized.startswith("$"):
        raise ValueError(f"Unsupported json path: {path}")

    current = data
    for key_match, index_match in _PATH_TOKEN_RE.findall(normalized[1:]):
        if key_match:
            if not isinstance(current, dict):
                return None
            current = current.get(key_match)
            if current is None:
                return None
            continue

        if not isinstance(current, list):
            return None
        index = int(index_match)
        if index >= len(current):
            return None
        current = current[index]
    return current


def coerce_text_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def extract_adapter_response(
    *,
    response_text: str,
    response_extract: dict | None,
    transport: str,
) -> dict[str, Any]:
    config = response_extract or default_response_extract_for_transport(transport)
    mode = str(config.get("mode") or "json_paths")

    if mode == "raw_text":
        return {
            "response_text": response_text,
            "response_error": None,
            "tool_calls": None,
        }

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        return {
            "response_text": None,
            "response_error": f"Failed to parse JSON response for extraction: {exc}",
            "tool_calls": None,
        }

    extracted_text = coerce_text_value(extract_json_path_value(payload, config.get("text_path")))
    extracted_error = coerce_text_value(extract_json_path_value(payload, config.get("error_path")))
    tool_calls = extract_json_path_value(payload, config.get("tool_calls_path"))

    if extracted_text is None and extracted_error is None:
        return {
            "response_text": None,
            "response_error": "Response extraction did not match any configured path",
            "tool_calls": tool_calls,
        }

    return {
        "response_text": extracted_text,
        "response_error": extracted_error,
        "tool_calls": tool_calls,
    }
