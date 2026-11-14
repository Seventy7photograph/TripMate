# 文件说明：数据库迁移：0010_planning_graph_metrics。
"""Add LangGraph run metrics.

Revision ID: 0010_planning_graph_metrics
Revises: 0009_brief_parse_runs
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_planning_graph_metrics"
down_revision: str | None = "0009_brief_parse_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "tool_call_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "loop_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "loop_count")
    op.drop_column("agent_runs", "tool_call_count")
