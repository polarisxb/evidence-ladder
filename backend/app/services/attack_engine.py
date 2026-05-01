import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "attack_templates"


class AttackEngine:
    def __init__(self):
        self._templates: dict[str, dict] = {}
        self._load_templates()

    def _load_templates(self):
        if not TEMPLATES_DIR.exists():
            logger.warning("Attack templates directory not found: %s", TEMPLATES_DIR)
            return
        for fp in TEMPLATES_DIR.glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                category = data.get("category", fp.stem)
                self._templates[category] = data
            except Exception:
                logger.exception("Failed to load template %s", fp)

    def get_categories(self) -> list[dict]:
        result = []
        for cat, data in self._templates.items():
            result.append({
                "category": cat,
                "category_name": data.get("category_name", cat),
                "owasp_id": data.get("owasp_id", ""),
                "description": data.get("description", ""),
                "template_count": len(data.get("templates", [])),
            })
        return result

    def get_templates_by_category(self, category: str) -> list[dict] | None:
        data = self._templates.get(category)
        if data is None:
            return None
        return data.get("templates", [])

    def get_all_templates(self, categories: list[str] | None = None) -> list[dict]:
        """Return flattened list of all templates, optionally filtered by category."""
        result = []
        for cat, data in self._templates.items():
            if categories and "all" not in categories and cat not in categories:
                continue
            cat_info = {
                "category": cat,
                "category_name": data.get("category_name", cat),
                "owasp_id": data.get("owasp_id", ""),
            }
            for tpl in data.get("templates", []):
                result.append({**tpl, **cat_info})
        return result
