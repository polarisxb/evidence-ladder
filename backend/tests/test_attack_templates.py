"""Validate all attack template JSON files have correct structure."""
import json
import glob
import os

import pytest

TEMPLATES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "app", "attack_templates"
)


def _load_template_files() -> list[tuple[str, dict]]:
    files = glob.glob(os.path.join(TEMPLATES_DIR, "*.json"))
    result = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            result.append((os.path.basename(f), json.load(fh)))
    return result


TEMPLATE_FILES = _load_template_files()


@pytest.mark.parametrize("filename,data", TEMPLATE_FILES, ids=[t[0] for t in TEMPLATE_FILES])
class TestTemplateStructure:
    def test_has_category(self, filename: str, data: dict) -> None:
        assert "category" in data, f"{filename} missing 'category'"
        assert isinstance(data["category"], str)

    def test_has_category_name(self, filename: str, data: dict) -> None:
        assert "category_name" in data, f"{filename} missing 'category_name'"

    def test_has_templates_array(self, filename: str, data: dict) -> None:
        assert "templates" in data, f"{filename} missing 'templates'"
        assert isinstance(data["templates"], list)
        assert len(data["templates"]) > 0, f"{filename} has empty templates"

    def test_template_required_fields(self, filename: str, data: dict) -> None:
        for tpl in data["templates"]:
            assert "id" in tpl, f"{filename}: template missing 'id'"
            assert "name" in tpl, f"{filename}/{tpl.get('id')}: missing 'name'"
            assert "technique" in tpl, f"{filename}/{tpl.get('id')}: missing 'technique'"
            assert "payloads" in tpl, f"{filename}/{tpl.get('id')}: missing 'payloads'"

    def test_payloads_not_empty(self, filename: str, data: dict) -> None:
        for tpl in data["templates"]:
            payloads = tpl.get("payloads", [])
            assert len(payloads) > 0, f"{filename}/{tpl['id']}: no payloads"
            for i, p in enumerate(payloads):
                assert p.get("text", "").strip(), f"{filename}/{tpl['id']}/payload[{i}]: empty text"

    def test_no_duplicate_ids(self, filename: str, data: dict) -> None:
        ids = [t["id"] for t in data["templates"]]
        assert len(ids) == len(set(ids)), f"{filename}: duplicate template IDs found"
