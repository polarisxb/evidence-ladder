import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Adapter(Base):
    __tablename__ = "adapters"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(50), default="direct_http_adapter")
    transport: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    auth_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    session_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    invoke_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    response_extract: Mapped[dict] = mapped_column(JSON, nullable=False)
    probe_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    scans: Mapped[list["ScanTask"]] = relationship(back_populates="adapter")
