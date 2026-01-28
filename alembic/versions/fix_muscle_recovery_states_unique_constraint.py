"""Fix muscle recovery states unique constraint to be per user instead of global"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'fix_muscle_rec_unique'
down_revision: Union[str, Sequence[str], None] = 'e0787659d7a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint('uq_user_muscle', 'muscle_recovery_states', ['user_id', 'muscle'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_user_muscle', 'muscle_recovery_states', type_='unique')
