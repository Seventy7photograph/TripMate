# 文件说明：数据库迁移：0018_uploaded_assets。
"""Add secure uploaded asset metadata.

Revision ID: 0018_uploaded_assets
Revises: 0017_agent_model_configs
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_uploaded_assets"
down_revision: str | None = "0017_agent_model_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploaded_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=128), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'ready'"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_uploaded_assets_owner_created",
        "uploaded_assets",
        ["owner_id", "created_at"],
    )
    op.create_index(
        "ix_uploaded_assets_expires_at",
        "uploaded_assets",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_uploaded_assets_expires_at", table_name="uploaded_assets")
    op.drop_index("ix_uploaded_assets_owner_created", table_name="uploaded_assets")
    op.drop_table("uploaded_assets")
