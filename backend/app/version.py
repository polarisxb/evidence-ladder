"""Registered software name and version: the backend's single source.

The frontend carries the same version in ``frontend/package.json``;
``tests/test_version_consistency.py`` fails when the two drift apart, so the
API, the UI and the exported reports always show one name and one version.
"""

APP_FULL_NAME = "大模型应用多源证据分层安全评测平台"
APP_VERSION = "1.0.0"


def version_label(version: str = APP_VERSION) -> str:
    """``1.0.0`` -> ``V1.0``, the form used on the registration documents."""
    major, minor = version.split(".")[:2]
    return f"V{major}.{minor}"


APP_VERSION_LABEL = version_label()
