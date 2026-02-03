"""merge heads

Revision ID: 62d84e939d17
Revises: add_onboarding_support, add_rule_timestamps
Create Date: 2026-02-01 19:16:08.393378

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62d84e939d17'
down_revision: Union[str, Sequence[str], None] = ('add_onboarding_support', 'add_rule_timestamps')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
