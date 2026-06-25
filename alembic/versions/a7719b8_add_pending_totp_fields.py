"""add pending_totp fields to users table

Revision ID: a7719b8
Revises: 254b7e6cbcbb
Create Date: 2026-06-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7719b8'
down_revision: Union[str, None] = '254b7e6cbcbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('pending_totp_secret', sa.String(64), nullable=True))
    op.add_column('users', sa.Column('pending_totp_expires_at', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'pending_totp_expires_at')
    op.drop_column('users', 'pending_totp_secret')
