from __future__ import annotations

import json
from pathlib import Path

from app.services.experiment_driver import compute_model_matrix_hash


RELAY_PROVIDER_ID = "b98979c7-bf60-4df0-976c-67b28272163b"
TARGET_VERSION = "gpt-5.4"


def _matrix(*, judge_version: str, verifier_version: str) -> dict[str, object]:
    models = [
        {
            "model_id": f"relay-{TARGET_VERSION}-target",
            "provider_id": RELAY_PROVIDER_ID,
            "pinned_version": TARGET_VERSION,
            "expected_returned_model": TARGET_VERSION,
            "role": "target",
        },
        {
            "model_id": f"relay-{judge_version}-judge",
            "provider_id": RELAY_PROVIDER_ID,
            "pinned_version": judge_version,
            "expected_returned_model": judge_version,
            "role": "judge",
        },
        {
            "model_id": f"relay-{verifier_version}-verifier",
            "provider_id": RELAY_PROVIDER_ID,
            "pinned_version": verifier_version,
            "expected_returned_model": verifier_version,
            "role": "verifier",
        },
    ]
    allow_rolling_aliases = False
    return {
        "matrix_version": "retest-model-matrix.v1",
        "content_hash": compute_model_matrix_hash(
            models,
            allow_rolling_aliases=allow_rolling_aliases,
        ),
        "models": models,
        "allow_rolling_aliases": allow_rolling_aliases,
    }


def main() -> None:
    configurations = {
        "formal_pilot_j55_v54_models.json": _matrix(
            judge_version="gpt-5.5",
            verifier_version="gpt-5.4",
        ),
        "formal_pilot_j54_v55_models.json": _matrix(
            judge_version="gpt-5.4",
            verifier_version="gpt-5.5",
        ),
    }
    for filename, payload in configurations.items():
        output = Path("experiments") / filename
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{output}: {payload['content_hash']}")


if __name__ == "__main__":
    main()
