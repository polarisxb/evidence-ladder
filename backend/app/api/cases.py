from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.database import get_db
from app.models import AttackCase, ScanTask
from app.services.case_serializer import serialize_attack_case_detail, serialize_attack_cases

router = APIRouter()


@router.get("/scans/{scan_id}/cases", response_model=dict)
async def list_scan_cases(scan_id: str, db: AsyncSession = Depends(get_db)):
    scan_exists = await db.execute(select(ScanTask.id).where(ScanTask.id == scan_id))
    if scan_exists.scalar_one_or_none() is None:
        raise AppException(404, "Scan not found")

    result = await db.execute(
        select(AttackCase)
        .where(AttackCase.scan_task_id == scan_id)
        .options(
            selectinload(AttackCase.variants),
            selectinload(AttackCase.legacy_attack_result),
        )
        .order_by(AttackCase.created_at.desc())
    )
    attack_cases = result.scalars().all()
    return {"data": serialize_attack_cases(attack_cases), "message": "ok"}


@router.get("/cases/{case_id}", response_model=dict)
async def get_case_detail(case_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AttackCase)
        .where(AttackCase.id == case_id)
        .options(
            selectinload(AttackCase.variants),
            selectinload(AttackCase.legacy_attack_result),
        )
    )
    attack_case = result.scalar_one_or_none()
    if not attack_case:
        raise AppException(404, "Attack case not found")
    return {"data": serialize_attack_case_detail(attack_case), "message": "ok"}
