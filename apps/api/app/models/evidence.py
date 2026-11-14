# 文件说明：SQLAlchemy 数据模型：evidence。
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    __table_args__ = (
        CheckConstraint(
            "fact_type IN ("
            "'place_fact', 'weather', 'transport', 'lodging_area', "
            "'meal', 'safety', 'altitude', 'attachment'"
            ")",
            name="ck_evidence_records_fact_type",
        ),
        CheckConstraint(
            "freshness IN ('live', 'cached', 'stale', 'mock', 'unknown')",
            name="ck_evidence_records_freshness",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_evidence_records_confidence",
        ),
        Index(
            "ix_evidence_records_owner_trip_fact",
            "owner_id",
            "trip_id",
            "fact_type",
        ),
        Index("ix_evidence_records_valid_until", "valid_until"),
        Index(
            "uq_evidence_records_owner_provider_record",
            "owner_id",
            "fact_type",
            "provider",
            "provider_record_id",
            unique=True,
            postgresql_where=text(
                "trip_id IS NULL AND provider_record_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_evidence_records_trip_provider_record",
            "owner_id",
            "trip_id",
            "fact_type",
            "provider",
            "provider_record_id",
            unique=True,
            postgresql_where=text(
                "trip_id IS NOT NULL AND provider_record_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    trip_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
    )
    fact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_record_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    freshness: Mapped[str] = mapped_column(String(16), nullable=False)
    license_scope: Mapped[str | None] = mapped_column(String(120))
    raw_hash: Mapped[str | None] = mapped_column(String(64))
    value: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
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
