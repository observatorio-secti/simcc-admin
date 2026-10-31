"""drop_users_and_oauth_accounts

Revision ID: c1f54a8e9902
Revises: b7c4e91a2d01
Create Date: 2026-10-31 13:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f54a8e9902'
down_revision: Union[str, Sequence[str], None] = 'b7c4e91a2d01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop local user and oauth tables as auth is delegated to observatorio-idp."""
    op.execute("DROP TABLE IF EXISTS oauth_accounts CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")


def downgrade() -> None:
    """Recreate users and oauth_accounts if needed."""
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('password', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('role', sa.String(), server_default='DEFAULT', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )
    op.create_table(
        'oauth_accounts',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_user_id', name='uq_provider_user'),
    )
