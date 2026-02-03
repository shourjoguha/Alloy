"""add_onboarding_support

Revision ID: add_onboarding_support
Revises: add_favorites_table
Create Date: 2026-01-31 00:00:00.000000

"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_onboarding_support'
down_revision: Union[str, Sequence[str], None] = 'add_favorites_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add onboarding columns to user_profiles and create onboarding_responses table."""
    
    op.add_column(
        'user_profiles',
        sa.Column('onboarding_completed_at', sa.DateTime(), nullable=True)
    )
    
    op.add_column(
        'user_profiles',
        sa.Column('onboarding_version', sa.String(length=50), nullable=True)
    )
    
    op.add_column(
        'user_profiles',
        sa.Column('equipment_familiarity', sa.JSON(), nullable=True)
    )
    
    op.add_column(
        'user_profiles',
        sa.Column('athletic_background', sa.JSON(), nullable=True)
    )
    
    op.add_column(
        'user_profiles',
        sa.Column('gym_comfort_level', sa.String(length=50), nullable=True)
    )
    
    op.create_table(
        'onboarding_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.String(length=100), nullable=False),
        sa.Column('answer_value', sa.JSON(), nullable=True),
        sa.Column('answered_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('question_set_version', sa.String(length=50), server_default='v1', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='fk_onboarding_responses_user_id'),
        sa.PrimaryKeyConstraint('id', name='pk_onboarding_responses')
    )
    op.create_index('ix_onboarding_responses_user_id', 'onboarding_responses', ['user_id'])
    op.create_index('ix_onboarding_responses_question_id', 'onboarding_responses', ['question_id'])
    op.create_index('idx_onboarding_user_version', 'onboarding_responses', ['user_id', 'question_set_version'])
    
    op.execute(
        "UPDATE user_profiles SET onboarding_completed_at = now(), onboarding_version = 'pre-onboarding-v1' WHERE onboarding_completed_at IS NULL"
    )


def downgrade() -> None:
    """Remove onboarding support."""
    
    op.drop_index('idx_onboarding_user_version', table_name='onboarding_responses')
    op.drop_index('ix_onboarding_responses_question_id', table_name='onboarding_responses')
    op.drop_index('ix_onboarding_responses_user_id', table_name='onboarding_responses')
    op.drop_table('onboarding_responses')
    
    op.drop_column('user_profiles', 'gym_comfort_level')
    op.drop_column('user_profiles', 'athletic_background')
    op.drop_column('user_profiles', 'equipment_familiarity')
    op.drop_column('user_profiles', 'onboarding_version')
    op.drop_column('user_profiles', 'onboarding_completed_at')
