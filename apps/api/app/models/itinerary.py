# 文件说明：SQLAlchemy 数据模型：itinerary。
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TripDay(Base):
    __tablename__ = "trip_days"
    __table_args__ = (
        CheckConstraint("day_index > 0", name="ck_trip_days_day_index"),
        Index("uq_trip_days_trip_date", "trip_id", "date", unique=True),
        Index("ix_trip_days_trip_date", "trip_id", "date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    trip_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    theme: Mapped[str | None] = mapped_column(String(160))
    leg_modes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
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


class ItineraryStop(Base):
    __tablename__ = "itinerary_stops"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes > 0 AND duration_minutes <= 1440",
            name="ck_itinerary_stops_duration",
        ),
        CheckConstraint(
            "estimated_cost_minor >= 0",
            name="ck_itinerary_stops_cost",
        ),
        CheckConstraint("order_index >= 0", name="ck_itinerary_stops_order"),
        Index("uq_itinerary_stops_day_order", "day_id", "order_index", unique=True),
        Index("ix_itinerary_stops_day_order", "day_id", "order_index"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    day_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trip_days.id", ondelete="CASCADE"),
        nullable=False,
    )
    place_id: Mapped[str] = mapped_column(String(200), nullable=False)
    place_name: Mapped[str | None] = mapped_column(String(200))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    coordinate_system: Mapped[str | None] = mapped_column(String(16))
    source: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
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
