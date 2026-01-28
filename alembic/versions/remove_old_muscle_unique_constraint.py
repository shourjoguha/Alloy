"""Remove old single-column unique constraint on muscle column"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'remove_old_muscle_unique'
down_revision: Union[str, Sequence[str], None] = 'fix_muscle_rec_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Drop the old single-column unique index on muscle column.
    This was preventing multiple users from having the same muscle in their recovery states.
    The composite unique constraint (user_id, muscle) already exists and is the correct one.
    """
    op.drop_index('ix_muscle_recovery_states_muscle', table_name='muscle_recovery_states')


def downgrade() -> None:
    """
    Re-add the old single-column unique index (not recommended as it breaks multi-user support).
    """
    op.create_unique_constraint('ix_muscle_recovery_states_muscle', 'muscle_recovery_states', ['muscle'])
