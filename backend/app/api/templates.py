import logging

from fastapi import APIRouter

from app.services.attack_engine import AttackEngine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=dict)
async def list_templates():
    """List all available attack template categories and their template counts."""
    engine = AttackEngine()
    categories = engine.get_categories()
    return {"data": categories, "message": "ok"}


@router.get("/{category}", response_model=dict)
async def get_category_templates(category: str):
    """Get all templates for a specific attack category."""
    engine = AttackEngine()
    templates = engine.get_templates_by_category(category)
    if templates is None:
        from app.core.exceptions import AppException
        raise AppException(404, f"Category '{category}' not found")
    return {"data": templates, "message": "ok"}
