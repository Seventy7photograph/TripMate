# 文件说明：数据库迁移：0028_mcp_connectors。
"""Add MCP connector state, quota, and health tracking.

Revision ID: 0028_mcp_connectors
Revises: 0027_external_fact_tools
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028_mcp_connectors"
down_revision: str | None = "0027_external_fact_tools"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_connectors",
        sa.Column("connector_id", sa.String(length=32), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default="disabled",
            nullable=False,
        ),
        sa.Column(
            "latency_ms",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daily_quota", sa.Integer(), nullable=False),
        sa.Column(
            "requests_today",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("quota_reset_at", sa.Date(), nullable=True),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False),
        sa.Column(
            "window_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "window_calls",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ("
            "'healthy', 'degraded', 'unavailable', "
            "'disabled', 'configured', 'unknown'"
            ")",
            name="ck_mcp_connectors_status",
        ),
        sa.CheckConstraint(
            "latency_ms >= 0 AND requests_today >= 0 AND daily_quota > 0 "
            "AND window_calls >= 0 AND rate_limit_per_minute > 0",
            name="ck_mcp_connectors_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("connector_id"),
    )


def downgrade() -> None:
    op.drop_table("mcp_connectors")
