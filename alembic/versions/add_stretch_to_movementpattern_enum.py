"""add stretch to movementpattern enum

Revision ID: add_stretch_enum
Revises:
Create Date: 2026-02-02

"""
from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa


revision: str = 'add_stretch_enum'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'stretch' value to movementpattern enum."""
    op.execute("ALTER TYPE movementpattern ADD VALUE 'stretch' AFTER 'cardio'")


def downgrade() -> None:
    """Remove 'stretch' value from movementpattern enum."""
    pass
