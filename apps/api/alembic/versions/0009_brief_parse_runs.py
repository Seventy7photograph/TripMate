# 文件说明：数据库迁移：0009_brief_parse_runs。
"""Support standalone brief parsing agent runs.

Revision ID: 0009_brief_parse_runs
Revises: 0008_agent_runs
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_brief_parse_runs"
down_revision: str | None = "0008_agent_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "purpose",
            sa.String(length=32),
            server_default="planning",
            nullable=False,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "provider",
            sa.String(length=40),
            server_default="mock",
            nullable=False,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "latency_ms",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.alter_column("agent_runs", "trip_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM agent_runs WHERE trip_id IS NULL")
    op.alter_column("agent_runs", "trip_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("agent_runs", "latency_ms")
    op.drop_column("agent_runs", "provider")
    op.drop_column("agent_runs", "purpose")
