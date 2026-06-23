"""add user.balance and log.cost fields

Revision ID: 4125d916f2eb
Revises: 11cc9084984c
Create Date: 2026-06-23 13:47:20.903784
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4125d916f2eb'
down_revision: Union[str, None] = '11cc9084984c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('logs', sa.Column('cost', sa.BigInteger(), nullable=False, server_default=sa.text('0')))
    op.add_column('users', sa.Column('balance', sa.BigInteger(), nullable=False, server_default=sa.text('0')))


def downgrade() -> None:
    op.drop_column('users', 'balance')
    op.drop_column('logs', 'cost')
    # ### end Alembic commands ###
