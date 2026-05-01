import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.database import get_db
from app.models import ScanTask, AttackResult
from app.core.frameworks import (
    OWASP_LLM_TOP10,
    MITRE_ATLAS_TECHNIQUES,
    CATEGORY_TO_OWASP,
    CATEGORY_TO_ATLAS,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/overview", response_model=dict)
async def get_overview_stats(db: AsyncSession = Depends(get_db)):
    total_scans = (await db.execute(select(func.count(ScanTask.id)))).scalar() or 0

    completed_scans = (
        await db.execute(
            select(func.count(ScanTask.id)).where(ScanTask.status == "completed")
        )
    ).scalar() or 0

    total_attacks = (await db.execute(select(func.count(AttackResult.id)))).scalar() or 0

    successful_attacks = (
        await db.execute(
            select(func.count(AttackResult.id)).where(AttackResult.attack_successful == True)
        )
    ).scalar() or 0

    avg_score = (
        await db.execute(
            select(func.avg(ScanTask.overall_score)).where(ScanTask.overall_score.isnot(None))
        )
    ).scalar()

    return {
        "data": {
            "total_scans": total_scans,
            "completed_scans": completed_scans,
            "total_attacks": total_attacks,
            "successful_attacks": successful_attacks,
            "avg_score": round(avg_score, 1) if avg_score else None,
            "attack_success_rate": round(successful_attacks / total_attacks * 100, 1) if total_attacks > 0 else 0,
        },
        "message": "ok",
    }


@router.get("/score-trend", response_model=dict)
async def get_score_trend(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScanTask.id, ScanTask.name, ScanTask.overall_score, ScanTask.created_at)
        .where(ScanTask.status == "completed")
        .order_by(ScanTask.created_at.desc())
        .limit(limit)
    )
    rows = list(reversed(result.all()))
    return {
        "data": [
            {
                "scan_id": r.id,
                "name": r.name,
                "score": r.overall_score,
                "date": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "message": "ok",
    }


@router.get("/risk-distribution", response_model=dict)
async def get_risk_distribution(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            AttackResult.risk_level,
            func.count(AttackResult.id).label("count"),
        )
        .where(AttackResult.attack_successful == True)
        .group_by(AttackResult.risk_level)
    )
    rows = result.all()
    distribution = {r.risk_level: r.count for r in rows}
    return {
        "data": {
            "critical": distribution.get("critical", 0),
            "high": distribution.get("high", 0),
            "medium": distribution.get("medium", 0),
            "low": distribution.get("low", 0),
        },
        "message": "ok",
    }


@router.get("/category-success-rate", response_model=dict)
async def get_category_success_rate(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            AttackResult.category,
            func.count(AttackResult.id).label("total"),
            func.sum(case((AttackResult.attack_successful == True, 1), else_=0)).label("successful"),
        )
        .group_by(AttackResult.category)
    )
    rows = result.all()
    return {
        "data": [
            {
                "category": r.category,
                "total": r.total,
                "successful": r.successful,
                "rate": round(r.successful / r.total * 100, 1) if r.total > 0 else 0,
            }
            for r in rows
        ],
        "message": "ok",
    }


@router.get("/frameworks", response_model=dict)
async def get_frameworks():
    owasp_items = list(OWASP_LLM_TOP10.values())
    atlas_items = list(MITRE_ATLAS_TECHNIQUES.values())
    return {
        "data": {
            "owasp": owasp_items,
            "atlas": atlas_items,
            "category_owasp_map": CATEGORY_TO_OWASP,
            "category_atlas_map": CATEGORY_TO_ATLAS,
        },
        "message": "ok",
    }


@router.get("/compliance/{scan_id}", response_model=dict)
async def get_compliance_score(scan_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScanTask)
        .where(ScanTask.id == scan_id)
        .options(selectinload(ScanTask.results))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise AppException(404, "Scan not found")

    tested_categories = {r.category for r in task.results}
    tested_owasp = {CATEGORY_TO_OWASP.get(c) for c in tested_categories} - {None}
    tested_atlas = set()
    for c in tested_categories:
        tested_atlas.update(CATEGORY_TO_ATLAS.get(c, []))

    testable_owasp = {k for k, v in OWASP_LLM_TOP10.items() if v["testable"]}

    owasp_coverage = len(tested_owasp & testable_owasp) / len(testable_owasp) * 100 if testable_owasp else 0
    atlas_coverage = len(tested_atlas) / len(MITRE_ATLAS_TECHNIQUES) * 100 if MITRE_ATLAS_TECHNIQUES else 0

    owasp_results: list[dict] = []
    for oid, entry in OWASP_LLM_TOP10.items():
        cat_results = [r for r in task.results if CATEGORY_TO_OWASP.get(r.category) == oid]
        total = len(cat_results)
        passed = sum(1 for r in cat_results if not r.attack_successful)
        owasp_results.append({
            "id": oid,
            "name": entry["name"],
            "testable": entry["testable"],
            "tested": total > 0,
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "score": round(passed / total * 100, 1) if total > 0 else None,
        })

    return {
        "data": {
            "owasp_coverage": round(owasp_coverage, 1),
            "atlas_coverage": round(atlas_coverage, 1),
            "owasp_results": owasp_results,
            "tested_atlas_ids": sorted(tested_atlas),
            "overall_score": task.overall_score,
        },
        "message": "ok",
    }


@router.get("/calibration/latest", response_model=dict)
async def get_latest_calibration_summary(db: AsyncSession = Depends(get_db)):
    """Return the latest completed calibration run summary, or null if none exists."""
    from sqlalchemy import select as _select
    from app.models.judge_calibration_run import JudgeCalibrationRun
    result = await db.execute(
        _select(JudgeCalibrationRun)
        .where(JudgeCalibrationRun.status == "completed")
        .order_by(JudgeCalibrationRun.completed_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return {"data": None, "message": "no calibration runs available"}
    return {
        "data": {
            "run_id": run.id,
            "name": run.name,
            "sample_count": run.sample_count,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "summary": run.summary_json,
        },
        "message": "ok",
    }


@router.get("/compare", response_model=dict)
async def compare_scans(
    scan_a: str,
    scan_b: str,
    db: AsyncSession = Depends(get_db),
):
    result_a = await db.execute(
        select(ScanTask).where(ScanTask.id == scan_a).options(selectinload(ScanTask.results))
    )
    task_a = result_a.scalar_one_or_none()
    if not task_a:
        raise AppException(404, f"Scan {scan_a} not found")

    result_b = await db.execute(
        select(ScanTask).where(ScanTask.id == scan_b).options(selectinload(ScanTask.results))
    )
    task_b = result_b.scalar_one_or_none()
    if not task_b:
        raise AppException(404, f"Scan {scan_b} not found")

    def _summarize(task: ScanTask) -> dict:
        cats: dict[str, dict] = {}
        for r in task.results:
            if r.category not in cats:
                cats[r.category] = {"total": 0, "successful": 0}
            cats[r.category]["total"] += 1
            if r.attack_successful:
                cats[r.category]["successful"] += 1

        return {
            "scan_id": task.id,
            "name": task.name,
            "overall_score": task.overall_score,
            "total_attacks": task.total_attacks,
            "vulnerabilities_found": task.vulnerabilities_found,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "categories": {
                cat: {
                    "total": info["total"],
                    "successful": info["successful"],
                    "rate": round(info["successful"] / info["total"] * 100, 1) if info["total"] > 0 else 0,
                }
                for cat, info in cats.items()
            },
        }

    a_summary = _summarize(task_a)
    b_summary = _summarize(task_b)

    a_vuln_names = {r.attack_name for r in task_a.results if r.attack_successful}
    b_vuln_names = {r.attack_name for r in task_b.results if r.attack_successful}

    return {
        "data": {
            "scan_a": a_summary,
            "scan_b": b_summary,
            "score_diff": round((b_summary["overall_score"] or 0) - (a_summary["overall_score"] or 0), 1),
            "new_vulnerabilities": sorted(b_vuln_names - a_vuln_names),
            "fixed_vulnerabilities": sorted(a_vuln_names - b_vuln_names),
            "persistent_vulnerabilities": sorted(a_vuln_names & b_vuln_names),
        },
        "message": "ok",
    }
