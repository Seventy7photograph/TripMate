# 文件说明：数据库迁移：0015_user_memories。
"""Add user-authorized travel memories with pgvector retrieval.

Revision ID: 0015_user_memories
Revises: 0014_favorites_shares
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0015_user_memories"
down_revision: str | None = "0014_favorites_shares"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "user_memories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(64), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            server_default=sa.text("'user'"),
            nullable=False,
        ),
        sa.Column(
            "consent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_memories_owner_enabled",
        "user_memories",
        ["owner_id", "enabled"],
    )
    op.create_index(
        "ix_user_memories_owner_updated",
        "user_memories",
        ["owner_id", "updated_at"],
    )
    op.execute(
        "CREATE INDEX ix_user_memories_embedding_hnsw "
        "ON user_memories USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_user_memories_embedding_hnsw", table_name="user_memories")
    op.drop_index("ix_user_memories_owner_updated", table_name="user_memories")
    op.drop_index("ix_user_memories_owner_enabled", table_name="user_memories")
    op.drop_table("user_memories")
