"""create_admins_table

Revision ID: d8a2c3e4f501
Revises: c1f54a8e9902
Create Date: 2026-11-22 05:32:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8a2c3e4f501"
down_revision: str | Sequence[str] | None = "c1f54a8e9902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create admins table for SimCC admin authorization."""
    op.create_table(
        "admins",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("sub", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sub"),
    )
    op.create_index("ix_admins_sub", "admins", ["sub"], unique=True)


def downgrade() -> None:
    """Drop admins table."""
    op.drop_index("ix_admins_sub", table_name="admins")
    op.drop_table("admins")
