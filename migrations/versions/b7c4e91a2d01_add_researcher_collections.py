"""add_researcher_collections

Revision ID: b7c4e91a2d01
Revises: 3e83d2129a16
Create Date: 2026-10-30 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c4e91a2d01"
down_revision: str | Sequence[str] | None = "3e83d2129a16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Cria academic.collections
    op.create_table(
        "collections",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "refresh_interval_days",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "refresh_interval_days >= 1",
            name="ck_academic_collections_refresh_interval",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        schema="academic",
    )
    op.create_index(
        op.f("ix_academic_collections_slug"),
        "collections",
        ["slug"],
        unique=True,
        schema="academic",
    )
    op.create_index(
        "uq_academic_collections_default",
        "collections",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        schema="academic",
    )

    # 2. Cria academic.researcher_collections
    op.create_table(
        "researcher_collections",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("researcher_id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["academic.collections.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["researcher_id"],
            ["academic.researchers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "researcher_id", "collection_id", name="uq_researcher_collection"
        ),
        schema="academic",
    )

    # 3. Seed inicial da coleção padrão 'simcc' e da coleção 'fomento'
    op.execute("""
        INSERT INTO academic.collections (id, slug, name, description, refresh_interval_days, is_default, created_at)
        VALUES 
            (gen_random_uuid(), 'simcc', 'SimCC', 'Coleção principal de pesquisadores do SimCC', 1, true, now()),
            (gen_random_uuid(), 'fomento', 'Fapesb Fomento', 'Coleção de bolsistas e pesquisadores do Fomento Fapesb', 30, false, now())
        ON CONFLICT (slug) DO NOTHING;
    """)

    # 4. Backfill de pesquisadores existentes para a coleção padrão 'simcc'
    op.execute("""
        INSERT INTO academic.researcher_collections (id, researcher_id, collection_id, attributes, created_at)
        SELECT 
            gen_random_uuid(), 
            r.id, 
            c.id, 
            '{}'::jsonb, 
            now()
        FROM academic.researchers r
        CROSS JOIN academic.collections c
        WHERE c.slug = 'simcc'
        ON CONFLICT (researcher_id, collection_id) DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_table("researcher_collections", schema="academic")
    op.drop_index(
        "uq_academic_collections_default",
        table_name="collections",
        schema="academic",
    )
    op.drop_index(
        op.f("ix_academic_collections_slug"),
        table_name="collections",
        schema="academic",
    )
    op.drop_table("collections", schema="academic")
