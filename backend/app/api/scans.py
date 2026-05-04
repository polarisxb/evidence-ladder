import logging

from fastapi import APIRouter, BackgroundTasks, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.database import get_db
from app.models import ScanTask
from app.models.attack_case import AttackCase
from app.schemas.scan import ScanCreate, ScanResponse, ScanProgress
from app.services.adapter_executor import get_adapter_or_raise
from app.services.llm_client import (
    LLMConfigurationError,
    ProviderClientInfo,
    call_chat,
    fetch_openai_compatible_model_ids,
    get_provider_by_id,
)
from app.services.autotest_retest_runs import record_retest_run_for_scan
from app.services.scan_recovery import finalize_stuck_scan_from_db
from app.services.scan_runner import run_scan
from app.services.url_guard import validate_target_url

logger = logging.getLogger(__name__)
router = APIRouter()

_ws_clients: dict[str, list[WebSocket]] = {}


async def _validate_provider_model(
    info: ProviderClientInfo,
    model_name: str,
    *,
    label: str,
    json_mode: bool = False,
) -> None:
    """Reject obvious provider/model mismatches before a scan is persisted."""
    model = model_name.strip()
    if not model or info.provider_type == "custom":
        return

    if info.provider_type != "claude":
        try:
            available_models = await fetch_openai_compatible_model_ids(
                api_key=info.api_key,
                provider_type=info.provider_type,
                base_url_override=info.base_url,
            )
        except LLMConfigurationError as exc:
            raise AppException(400, f"{label}: failed to verify selected model: {exc}") from exc

        if not available_models:
            raise AppException(400, f"{label}: selected provider did not return any chat models")

        if model not in available_models:
            raise AppException(
                400,
                f"{label}: model '{model}' is not available for selected provider ({info.provider_type})",
            )

    # Some providers list marketplace models before the account has activated
    # that product. Probe the exact model so scans fail early with a clear error.
    try:
        await call_chat(
            info,
            model,
            [{"role": "user", "content": 'Return a JSON object: {"ok": true}'}]
            if json_mode
            else [{"role": "user", "content": "Reply with OK."}],
            max_tokens=12 if json_mode else 2,
            temperature=0.0,
            json_mode=json_mode,
        )
    except Exception as exc:
        raise AppException(
            400,
            f"{label}: model '{model}' failed provider probe: {exc}",
        ) from exc


@router.post("", response_model=dict)
async def create_scan(
    body: ScanCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    resolved_target_url = body.target_url
    if body.target_type == "builtin_vulnerable":
        resolved_target_url = body.target_url or "builtin"
    elif body.target_type == "adapter":
        adapter = await get_adapter_or_raise(db, body.adapter_id or "")
        if not adapter.enabled:
            raise AppException(400, "Adapter is disabled")
        resolved_target_url = adapter.base_url

    # Stage 1.1b — SSRF guard. Skip the synthetic 'builtin' URL which is
    # not an actual fetchable endpoint (handled inside vulnerable_ai.py).
    if (
        resolved_target_url
        and body.target_type != "builtin_vulnerable"
        and resolved_target_url.lower().startswith(("http://", "https://"))
    ):
        validate_target_url(resolved_target_url)

    resolved_target_config = body.target_config.model_dump() if body.target_config else None
    resolved_judge_model = body.judge_model
    resolved_generation_model = body.generation_model

    async def _resolve_selected_provider_model(
        provider_id: str,
        *,
        role: str,
        label: str,
        requested_model: str | None = None,
    ) -> str:
        try:
            resolved = await get_provider_by_id(provider_id, role=role)
        except LLMConfigurationError as exc:
            raise AppException(400, f"{label}: {exc}") from exc
        if not resolved:
            raise AppException(400, f"{label}: selected provider was not found or is disabled")
        info, default_model = resolved

        selected_model = (requested_model or default_model).strip()
        await _validate_provider_model(info, selected_model, label=label, json_mode=role == "judge")
        return selected_model

    if body.judge_provider_id:
        resolved_judge_model = await _resolve_selected_provider_model(
            body.judge_provider_id,
            role="judge",
            label="Judge provider model resolution failed",
            requested_model=resolved_judge_model,
        )

    if body.generation_provider_id:
        resolved_generation_model = await _resolve_selected_provider_model(
            body.generation_provider_id,
            role="generation",
            label="Generation provider model resolution failed",
            requested_model=resolved_generation_model,
        )

    if (
        resolved_target_config
        and isinstance(resolved_target_config.get("provider_id"), str)
        and body.target_type in {"openai_compatible", "claude"}
    ):
        resolved_target_config["model"] = await _resolve_selected_provider_model(
            resolved_target_config["provider_id"],
            role="target",
            label="Target provider model resolution failed",
            requested_model=resolved_target_config.get("model"),
        )

    if (
        resolved_target_config
        and not (resolved_target_config.get("provider_id") or "").strip()
        and not (resolved_target_config.get("model") or "").strip()
        and body.target_type == "openai_compatible"
        and not (resolved_target_url or "").strip().startswith(("https://api.openai.com", "default"))
    ):
        raise AppException(
            400,
            "Custom OpenAI-compatible targets require an explicit model when no provider is selected.",
        )

    task = ScanTask(
        name=body.name,
        target_url=resolved_target_url,
        target_type=body.target_type,
        adapter_id=body.adapter_id,
        target_config=resolved_target_config,
        runtime_vars=body.runtime_vars or None,
        attack_categories=body.attack_categories,
        advanced_config=(
            body.advanced.model_dump(exclude_none=True, exclude_unset=True)
            if body.advanced
            else None
        ),
        judge_provider_id=body.judge_provider_id,
        judge_model=resolved_judge_model,
        generation_provider_id=body.generation_provider_id,
        generation_model=resolved_generation_model,
    )
    db.add(task)
    await db.flush()
    await record_retest_run_for_scan(task, db)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(run_scan, task.id, _ws_clients)
    logger.info("Created scan task %s targeting %s", task.id, task.target_url)
    return {"data": {"task_id": task.id}, "message": "Scan task created"}


@router.get("", response_model=dict)
async def list_scans(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    base = select(ScanTask)
    if status:
        base = base.where(ScanTask.status == status)
    if q:
        pattern = f"%{q}%"
        base = base.where(ScanTask.name.ilike(pattern) | ScanTask.target_url.ilike(pattern))

    offset = (page - 1) * page_size
    stmt = base.order_by(ScanTask.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar() or 0

    return {
        "data": [ScanResponse.model_validate(t) for t in tasks],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/batch-delete", response_model=dict)
async def batch_delete_scans(
    scan_ids: list[str],
    db: AsyncSession = Depends(get_db),
):
    deleted = 0
    for scan_id in scan_ids:
        result = await db.execute(
            select(ScanTask).where(ScanTask.id == scan_id).options(
                selectinload(ScanTask.results),
                selectinload(ScanTask.attack_cases).selectinload(AttackCase.variants),
            )
        )
        task = result.scalar_one_or_none()
        if task and task.status != "running":
            await db.delete(task)
            deleted += 1
    await db.commit()
    return {"data": {"deleted": deleted}, "message": f"{deleted} scans deleted"}


@router.post("/{task_id}/finalize-stuck", response_model=dict)
async def finalize_stuck_scan(task_id: str, db: AsyncSession = Depends(get_db)):
    """Mark a stuck `running` scan as completed using existing attack results (recovery / UI out of sync)."""
    data = await finalize_stuck_scan_from_db(task_id, db)
    return {"data": data, "message": "Scan marked completed from saved results"}


@router.post("/{task_id}/pause", response_model=dict)
async def pause_scan(task_id: str, db: AsyncSession = Depends(get_db)):
    """Stop the scan early and finalize a report from the results collected so far."""
    data = await finalize_stuck_scan_from_db(task_id, db)
    return {"data": data, "message": "Scan stopped and finalized from saved results"}


@router.post("/{task_id}/cancel", response_model=dict)
async def cancel_scan(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScanTask).where(ScanTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise AppException(404, "Scan task not found")
    if task.status not in ("pending", "running"):
        raise AppException(400, "Scan is not running")
    task.status = "cancelled"
    await db.commit()
    from app.services.scan_runner import signal_scan_stop
    signal_scan_stop(task_id)
    return {"data": {"task_id": task_id}, "message": "Scan cancelled"}


@router.delete("/{task_id}", response_model=dict)
async def delete_scan(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScanTask).where(ScanTask.id == task_id).options(
            selectinload(ScanTask.results),
            selectinload(ScanTask.attack_cases).selectinload(AttackCase.variants),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise AppException(404, "Scan task not found")
    if task.status == "running":
        raise AppException(400, "Cannot delete a running scan. Cancel it first.")
    await db.delete(task)
    await db.commit()
    return {"data": {"task_id": task_id}, "message": "Scan deleted"}


@router.post("/{task_id}/retry", response_model=dict)
async def retry_scan(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ScanTask).where(ScanTask.id == task_id))
    original = result.scalar_one_or_none()
    if not original:
        raise AppException(404, "Scan task not found")
    if original.status not in ("completed", "failed", "cancelled"):
        raise AppException(400, "Can only retry completed, failed, or cancelled scans")

    new_task = ScanTask(
        name=f"{original.name} (retry)",
        target_url=original.target_url,
        target_type=original.target_type,
        adapter_id=original.adapter_id,
        target_config=original.target_config,
        runtime_vars=original.runtime_vars,
        attack_categories=original.attack_categories,
        advanced_config=original.advanced_config,
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)

    background_tasks.add_task(run_scan, new_task.id, _ws_clients)
    return {"data": {"task_id": new_task.id}, "message": "Scan retry created"}


@router.get("/{task_id}", response_model=dict)
async def get_scan(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScanTask).where(ScanTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise AppException(404, "Scan task not found")
    return {"data": ScanResponse.model_validate(task), "message": "ok"}


@router.websocket("/ws/{task_id}")
async def scan_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    _ws_clients.setdefault(task_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients[task_id].remove(websocket)
        if not _ws_clients[task_id]:
            del _ws_clients[task_id]
