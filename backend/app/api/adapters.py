import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.models import Adapter
from app.schemas.adapter import (
    AdapterCreate,
    AdapterProbeTestResponse,
    AdapterResponse,
    AdapterProbeConfig,
    AdapterTestRequest,
    AdapterTestResponse,
    AdapterUpdate,
    ProbeTestRequest,
)
from app.services.adapter_executor import execute_adapter_request, get_adapter_or_raise
from app.services.probe_executor import execute_probe

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/adapters")


def _adapter_payload_from_schema(body: AdapterCreate | AdapterUpdate) -> dict:
    data = body.model_dump(exclude_none=True)
    if "auth_config" in data:
        data["auth_config"] = body.auth_config.model_dump(exclude_none=True) if body.auth_config else None
    if "session_config" in data:
        data["session_config"] = body.session_config.model_dump(exclude_none=True) if body.session_config else None
    if "invoke_config" in data:
        data["invoke_config"] = body.invoke_config.model_dump(exclude_none=True) if body.invoke_config else None
    if "response_extract" in data:
        data["response_extract"] = (
            body.response_extract.model_dump(exclude_none=True) if body.response_extract else None
        )
    if "probe_config" in data:
        data["probe_config"] = (
            body.probe_config.model_dump(exclude_none=True) if body.probe_config else None
        )
    return data


@router.post("", response_model=dict)
async def create_adapter(body: AdapterCreate, db: AsyncSession = Depends(get_db)):
    adapter = Adapter(**_adapter_payload_from_schema(body))
    db.add(adapter)
    await db.commit()
    await db.refresh(adapter)
    return {"data": AdapterResponse.model_validate(adapter), "message": "Adapter created"}


@router.get("", response_model=dict)
async def list_adapters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Adapter).order_by(Adapter.updated_at.desc()))
    adapters = result.scalars().all()
    return {
        "data": [AdapterResponse.model_validate(adapter) for adapter in adapters],
        "message": "ok",
    }


@router.get("/{adapter_id}", response_model=dict)
async def get_adapter(adapter_id: str, db: AsyncSession = Depends(get_db)):
    adapter = await get_adapter_or_raise(db, adapter_id)
    return {"data": AdapterResponse.model_validate(adapter), "message": "ok"}


@router.patch("/{adapter_id}", response_model=dict)
async def update_adapter(
    adapter_id: str,
    body: AdapterUpdate,
    db: AsyncSession = Depends(get_db),
):
    adapter = await get_adapter_or_raise(db, adapter_id)
    updates = _adapter_payload_from_schema(body)
    merged = {
        "name": adapter.name,
        "description": adapter.description,
        "mode": adapter.mode,
        "transport": adapter.transport,
        "base_url": adapter.base_url,
        "auth_config": adapter.auth_config,
        "session_config": adapter.session_config,
        "invoke_config": adapter.invoke_config,
        "response_extract": adapter.response_extract,
        "probe_config": adapter.probe_config,
        "enabled": adapter.enabled,
        **updates,
    }
    validated = AdapterCreate.model_validate(merged)
    payload = _adapter_payload_from_schema(validated)
    for field_name, value in payload.items():
        setattr(adapter, field_name, value)

    await db.commit()
    await db.refresh(adapter)
    return {"data": AdapterResponse.model_validate(adapter), "message": "Adapter updated"}


async def _resolve_test_adapter(body: AdapterTestRequest | ProbeTestRequest, db: AsyncSession) -> AdapterCreate | Adapter:
    if body.adapter is not None:
        return body.adapter
    if not body.adapter_id:
        raise AppException(400, "adapter_id or adapter is required")
    return await get_adapter_or_raise(db, body.adapter_id)


@router.post("/test", response_model=dict)
async def test_adapter(body: AdapterTestRequest, db: AsyncSession = Depends(get_db)):
    adapter = await _resolve_test_adapter(body, db)
    result = await execute_adapter_request(
        adapter,
        prompt=body.prompt,
        history=body.history,
        runtime_vars=body.runtime_vars,
        scan_id=body.scan_id,
        case_id=body.case_id,
        variant_type=body.variant_type,
    )
    return {"data": AdapterTestResponse.model_validate(result), "message": "Adapter test completed"}


@router.post("/probe/test", response_model=dict)
async def test_adapter_probe(body: ProbeTestRequest, db: AsyncSession = Depends(get_db)):
    adapter = await _resolve_test_adapter(body, db)
    probe_override = (
        AdapterProbeConfig.model_validate(body.probe_config.model_dump(exclude_none=True))
        if body.probe_config is not None
        else None
    )
    result = await execute_probe(
        adapter,
        probe_config=probe_override,
        runtime_vars=body.runtime_vars,
        session_id=body.session_id,
        scan_id=body.scan_id,
        case_id=body.case_id,
        variant_type=body.variant_type,
    )
    return {
        "data": AdapterProbeTestResponse.model_validate(result),
        "message": "Probe test completed",
    }
