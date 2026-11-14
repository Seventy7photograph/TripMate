# 文件说明：SQLAlchemy 数据模型：mcp_connector。

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class McpConnectorState(Base):
    __tablename__ = "mcp_connectors"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'healthy', 'degraded', 'unavailable', "
            "'disabled', 'configured', 'unknown'"
            ")",
            name="ck_mcp_connectors_status",
        ),
        CheckConstraint(
            "latency_ms >= 0 AND requests_today >= 0 AND daily_quota > 0 "
            "AND window_calls >= 0 AND rate_limit_per_minute > 0",
            name="ck_mcp_connectors_nonnegative",
        ),
    )

    connector_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="disabled",
        server_default="disabled",
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daily_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    requests_today: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    quota_reset_at: Mapped[date | None] = mapped_column(Date)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    window_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    window_calls: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
