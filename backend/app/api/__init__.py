from fastapi import APIRouter

from app.api import adapters, autotest, cases, judge_calibration, model_providers, reports, scans, settings, stats, targets, templates

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(adapters.router, tags=["adapters"])
api_router.include_router(autotest.router, prefix="/autotest", tags=["autotest"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(cases.router, tags=["cases"])
api_router.include_router(targets.router, prefix="/targets", tags=["targets"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(
    model_providers.router,
    prefix="/model-providers",
    tags=["model-providers"],
)
api_router.include_router(
    judge_calibration.router,
    prefix="/judge/calibration",
    tags=["judge-calibration"],
)
