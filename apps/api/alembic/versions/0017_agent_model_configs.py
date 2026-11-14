# 文件说明：数据库迁移：0017_agent_model_configs。
"""Add online per-stage model configuration.

Revision ID: 0017_agent_model_configs
Revises: 0016_admin_observability
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_agent_model_configs"
down_revision: str | None = "0016_admin_observability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_model_configs",
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("provider_profile", sa.String(length=16), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("stage"),
    )


def downgrade() -> None:
    op.drop_table("agent_model_configs")
