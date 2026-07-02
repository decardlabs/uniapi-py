"""add login lockout fields to users table

Revision ID: 582fd30bfb5b
Revises: cccd19f2a591
Create Date: 2026-07-02 10:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '582fd30bfb5b'
down_revision: Union[str, None] = 'cccd19f2a591'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('failed_login_attempts', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('locked_until', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('locked_until')
        batch_op.drop_column('failed_login_attempts')
