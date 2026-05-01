from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.autotest import AutoTestDraftRequest, AutoTestDraftResponse, AutoTestPlanRequest, AutoTestPlanResponse
from app.database import get_db
from app.services.autotest_planner import build_autotest_plan
from app.services.autotest_retest import build_quartet_retest_draft
from app.services.autotest_scan_builder import build_autotest_scan_draft
from app.services.autotest_summary import build_autotest_summary


router = APIRouter()


@router.post("/plan", response_model=dict)
async def create_autotest_plan(body: AutoTestPlanRequest):
    plan = build_autotest_plan(body.model_dump(exclude_none=True))
    return {
        "data": {
            "plan": AutoTestPlanResponse(**plan.to_dict()).model_dump(),
        },
        "message": "AutoTest plan generated",
    }


@router.post("/draft", response_model=dict)
async def create_autotest_scan_draft(body: AutoTestDraftRequest):
    plan, scan_config = build_autotest_scan_draft(body)
    draft = AutoTestDraftResponse(
        plan=AutoTestPlanResponse(**plan.to_dict()),
        scan_config=scan_config,
    )
    return {
        "data": draft.model_dump(),
        "message": "AutoTest scan draft generated",
    }


@router.get("/scans/{scan_id}/summary", response_model=dict)
async def get_autotest_scan_summary(scan_id: str, db: AsyncSession = Depends(get_db)):
    summary = await build_autotest_summary(scan_id, db)
    return {"data": summary.model_dump(), "message": "ok"}


@router.post("/scans/{scan_id}/retest-draft", response_model=dict)
async def create_autotest_retest_draft(scan_id: str, db: AsyncSession = Depends(get_db)):
    draft = await build_quartet_retest_draft(scan_id, db)
    return {"data": draft.model_dump(), "message": "AutoTest retest draft generated"}
