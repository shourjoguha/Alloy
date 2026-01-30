"""add_timestamps_to_user_movement_rules

Revision ID: add_rule_timestamps
Revises: add_circuit_mutual_exclusivity
Create Date: 2026-01-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_rule_timestamps'
down_revision: Union[str, Sequence[str], None] = 'add_circuit_mutual_exclusivity'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add created_at and updated_at timestamps to user_movement_rules table."""
    
    op.add_column('user_movement_rules', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('user_movement_rules', sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    op.execute("""
        UPDATE user_movement_rules 
        SET created_at = NOW(), updated_at = NOW()
        WHERE created_at IS NULL
    """)
    
    op.alter_column('user_movement_rules', 'created_at', nullable=False)
    op.alter_column('user_movement_rules', 'updated_at', nullable=False)
    
    op.create_index(
        'ix_user_movement_rules_user_type_created',
        'user_movement_rules',
        ['user_id', 'rule_type', 'created_at']
    )
    
    op.execute("""
        DELETE FROM user_movement_rules
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM user_movement_rules
            GROUP BY user_id, movement_id, rule_type
        )
    """)
    
    op.create_unique_constraint(
        'uq_user_movement_rule_type',
        'user_movement_rules',
        ['user_id', 'movement_id', 'rule_type']
    )


def downgrade() -> None:
    """Remove created_at and updated_at timestamps from user_movement_rules table."""
    
    op.drop_constraint('uq_user_movement_rule_type', 'user_movement_rules', type_='unique')
    op.drop_index('ix_user_movement_rules_user_type_created', table_name='user_movement_rules')
    op.alter_column('user_movement_rules', 'updated_at', nullable=True)
    op.alter_column('user_movement_rules', 'created_at', nullable=True)
    op.drop_column('user_movement_rules', 'updated_at')
    op.drop_column('user_movement_rules', 'created_at')
