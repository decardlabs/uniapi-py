"""add session_version to users

Revision ID: c8c4a8ff0bfa
Revises: cccd19f2a591
Create Date: 2026-06-30 22:33:42.239251
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8c4a8ff0bfa'
down_revision: Union[str, None] = 'cccd19f2a591'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('session_version', sa.Integer(), nullable=False, server_default=sa.text('1')))


def downgrade() -> None:
    op.drop_column('users', 'session_version')
