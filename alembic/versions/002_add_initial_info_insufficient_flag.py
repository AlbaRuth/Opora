"""
Add initial_info_insufficient flag to clinical_profiles.

Revision ID: 002
Revises: 001
Create Date: 2026-05-10 21:30:00
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add initial_info_insufficient column to clinical_profiles."""
    op.add_column(
        'clinical_profiles',
        sa.Column('initial_info_insufficient', sa.Boolean(), nullable=False, server_default='false'),
        schema='clinical'
    )


def downgrade() -> None:
    """Remove initial_info_insufficient column."""
    op.drop_column('clinical_profiles', 'initial_info_insufficient', schema='clinical')
