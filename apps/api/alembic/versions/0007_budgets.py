# 文件说明：数据库迁移：0007_budgets。
"""Create expenses table.

Revision ID: 0007_budgets
Revises: 0006_route_legs
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_budgets"
down_revision: str | None = "0006_route_legs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("payer_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_expenses_trip_date",
        "expenses",
        ["trip_id", "expense_date"],
        unique=False,
    )
    op.create_index(
        "ix_expenses_trip_category",
        "expenses",
        ["trip_id", "category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_expenses_trip_category", table_name="expenses")
    op.drop_index("ix_expenses_trip_date", table_name="expenses")
    op.drop_table("expenses")
