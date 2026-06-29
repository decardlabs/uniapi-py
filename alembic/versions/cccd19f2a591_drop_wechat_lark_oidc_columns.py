"""drop_wechat_lark_oidc_columns

Revision ID: cccd19f2a591
Revises: 306a8eeb6f40
Create Date: 2026-06-29 13:59:56.995320
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cccd19f2a591'
down_revision: Union[str, None] = '306a8eeb6f40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop unused OAuth columns — SQLite batch_alter_table handles table rebuild
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('wechat_id')
        batch_op.drop_column('lark_id')
        batch_op.drop_column('oidc_id')


def downgrade() -> None:
    # Restore passkey_credentials table
    op.create_table('passkey_credentials',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('credential_id', sa.VARCHAR(length=512), nullable=False),
    sa.Column('public_key', sa.TEXT(), nullable=False),
    sa.Column('sign_count', sa.INTEGER(), nullable=False),
    sa.Column('credential_name', sa.VARCHAR(length=128), nullable=False),
    sa.Column('transports', sa.VARCHAR(length=256), nullable=False),
    sa.Column('created_at', sa.BIGINT(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('credential_id')
    )
    op.create_index(op.f('ix_passkey_credentials_user_id'), 'passkey_credentials', ['user_id'], unique=False)

    # Restore columns
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('wechat_id', sa.VARCHAR(64), nullable=True))
        batch_op.add_column(sa.Column('lark_id', sa.VARCHAR(64), nullable=True))
        batch_op.add_column(sa.Column('oidc_id', sa.VARCHAR(64), nullable=True))
