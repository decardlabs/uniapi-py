"""merge login_lockout and session_version heads

Revision ID: 8bae083a0c2d
Revises: 582fd30bfb5b, c8c4a8ff0bfa
Create Date: 2026-07-02 13:52:46.382322
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8bae083a0c2d'
down_revision: Union[str, None] = ('582fd30bfb5b', 'c8c4a8ff0bfa')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
