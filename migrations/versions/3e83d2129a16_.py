"""empty message

Revision ID: 3e83d2129a16
Revises:
Create Date: 2026-10-02 10:51:06.460957

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e83d2129a16"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS academic")
    op.create_table(
        "institutions",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("acronym", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("acronym"),
        sa.UniqueConstraint("name"),
        schema="academic",
    )
    op.create_table(
        "researchers",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("lattes_id", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="academic",
    )
    op.create_index(
        op.f("ix_academic_researchers_lattes_id"),
        "researchers",
        ["lattes_id"],
        unique=True,
        schema="academic",
    )
    op.create_table(
        "users",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column(
            "role",
            sa.Enum("DEFAULT", "ADMIN", name="userrole"),
            server_default="DEFAULT",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "researcher_institutions",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("researcher_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["academic.institutions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["researcher_id"], ["academic.researchers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "researcher_id", "institution_id", name="uq_researcher_institution"
        ),
        schema="academic",
    )
    op.create_table(
        "oauth_accounts",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_user_id", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),
    )


def downgrade() -> None:
    op.drop_table("oauth_accounts")
    op.drop_table("researcher_institutions", schema="academic")
    op.drop_table("users")
    op.drop_index(
        op.f("ix_academic_researchers_lattes_id"),
        table_name="researchers",
        schema="academic",
    )
    op.drop_table("researchers", schema="academic")
    op.drop_table("institutions", schema="academic")
    op.execute("DROP SCHEMA IF EXISTS academic CASCADE")
