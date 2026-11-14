# 文件说明：数据库迁移：0019_favorite_organization。
"""Add favorite folders and notes.

Revision ID: 0019_favorite_organization
Revises: 0018_uploaded_assets
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_favorite_organization"
down_revision: str | None = "0018_uploaded_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "favorites",
        sa.Column(
            "folder",
            sa.String(length=80),
            server_default=sa.text("'默认收藏'"),
            nullable=False,
        ),
    )
    op.add_column(
        "favorites",
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_favorites_owner_folder_created",
        "favorites",
        ["owner_id", "folder", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_favorites_owner_folder_created",
        table_name="favorites",
    )
    op.drop_column("favorites", "note")
    op.drop_column("favorites", "folder")
