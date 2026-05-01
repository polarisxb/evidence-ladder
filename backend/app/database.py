from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_additive_scan_task_columns)
        await conn.run_sync(_ensure_additive_adapter_columns)
        await conn.run_sync(_ensure_additive_attack_case_columns)


def _ensure_additive_scan_task_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "scan_tasks" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("scan_tasks")}
    if "adapter_id" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN adapter_id VARCHAR(36)")
    if "runtime_vars" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN runtime_vars JSON")
    if "judge_provider_id" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN judge_provider_id VARCHAR(36)")
    if "judge_model" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN judge_model VARCHAR(255)")
    if "generation_provider_id" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN generation_provider_id VARCHAR(36)")
    if "generation_model" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN generation_model VARCHAR(255)")
    if "target_health" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN target_health VARCHAR(20)")
    if "health_probe_passed" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN health_probe_passed BOOLEAN")
    if "health_failure_reason" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN health_failure_reason TEXT")
    if "recent_health_signature" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN recent_health_signature TEXT")
    if "invalid_response_ratio" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE scan_tasks ADD COLUMN invalid_response_ratio FLOAT")


def _ensure_additive_adapter_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "adapters" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("adapters")}
    if "probe_config" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE adapters ADD COLUMN probe_config JSON")


def _ensure_additive_attack_case_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "attack_cases" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("attack_cases")}
    if "business_verification_status" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE attack_cases ADD COLUMN business_verification_status VARCHAR(50)")
    if "probe_summary" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE attack_cases ADD COLUMN probe_summary JSON")
    if "probe_evidence_json" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE attack_cases ADD COLUMN probe_evidence_json JSON")
    if "judge_snapshot" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE attack_cases ADD COLUMN judge_snapshot JSON")
    if "review_required" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE attack_cases ADD COLUMN review_required BOOLEAN")
    if "reportable" not in columns:
        sync_conn.exec_driver_sql("ALTER TABLE attack_cases ADD COLUMN reportable BOOLEAN")
