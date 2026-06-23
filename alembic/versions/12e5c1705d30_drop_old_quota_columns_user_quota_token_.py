"""drop old quota columns (user.quota, token.*quota*, log.quota)

Revision ID: 12e5c1705d30
Revises: 4125d916f2eb
Create Date: 2026-06-23 14:50:18.930354
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12e5c1705d30'
down_revision: Union[str, None] = '4125d916f2eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('logs', 'quota')
    op.drop_column('tokens', 'used_quota')
    op.drop_column('tokens', 'remain_quota')
    op.drop_column('tokens', 'unlimited_quota')
    op.drop_column('users', 'quota')
    op.drop_column('users', 'used_quota')


def downgrade() -> None:
    op.add_column('users', sa.Column('used_quota', sa.BIGINT(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('quota', sa.BIGINT(), server_default='0', nullable=False))
    op.add_column('tokens', sa.Column('unlimited_quota', sa.BOOLEAN(), server_default='0', nullable=False))
    op.add_column('tokens', sa.Column('remain_quota', sa.BIGINT(), server_default='0', nullable=False))
    op.add_column('tokens', sa.Column('used_quota', sa.BIGINT(), server_default='0', nullable=False))
    op.add_column('logs', sa.Column('quota', sa.INTEGER(), server_default='0', nullable=False))
    # ### end Alembic commands ###
