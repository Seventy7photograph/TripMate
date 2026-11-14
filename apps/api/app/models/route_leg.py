# 文件说明：SQLAlchemy 数据模型：route_leg。
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RouteLeg(Base):
    __tablename__ = "route_legs"
    __table_args__ = (
        Index(
            "uq_route_legs_day_pair_mode",
            "day_id",
            "from_stop_id",
            "to_stop_id",
            "mode",
            unique=True,
        ),
        Index("ix_route_legs_day", "day_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    day_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trip_days.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_stop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("itinerary_stops.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_stop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("itinerary_stops.id", ondelete="CASCADE"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    distance_m: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    polyline: Mapped[str | None] = mapped_column(Text)
    source: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
