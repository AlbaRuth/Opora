"""
Add intake stage fields for clinical intake workflow.

Revision ID: 003
Revises: 002
Create Date: 2026-01-03 00:00:00.000000

Adds flow phase tracking and clinical hypothesis fields for the
intake stage feature.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add intake stage columns to therapy_sessions
    session_columns = [
        ("flow_phase", sa.String(20), "'therapy'"),
        ("intake_user_turns", sa.Integer(), "0"),
        ("intake_completed_at", sa.DateTime(timezone=True), None),
    ]
    
    for col_name, col_type, default in session_columns:
        conn = op.get_bind()
        result = conn.execute(
            sa.text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'therapy_sessions' AND column_name = :col
            """),
            {"col": col_name}
        )
        
        if result.scalar_one_or_none() is None:
            kwargs = {"nullable": True}
            if default is not None:
                kwargs["server_default"] = sa.text(default)
                kwargs["nullable"] = False
            op.add_column("therapy_sessions", sa.Column(col_name, col_type, **kwargs))
    
    # Set default values for existing rows
    op.execute(
        sa.text("""
            UPDATE therapy_sessions
            SET flow_phase = COALESCE(flow_phase, 'therapy'),
                intake_user_turns = COALESCE(intake_user_turns, 0)
        """)
    )
    
    # Add intake hypothesis fields to users
    user_columns = [
        ("intake_hypothesis", sa.Text(), None),
        ("intake_hypothesis_explanation", sa.Text(), None),
    ]
    
    for col_name, col_type, default in user_columns:
        conn = op.get_bind()
        result = conn.execute(
            sa.text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = :col
            """),
            {"col": col_name}
        )
        
        if result.scalar_one_or_none() is None:
            op.add_column("users", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    # Remove intake stage columns
    op.drop_column("therapy_sessions", "intake_completed_at")
    op.drop_column("therapy_sessions", "intake_user_turns")
    op.drop_column("therapy_sessions", "flow_phase")
    
    # Remove intake hypothesis columns
    op.drop_column("users", "intake_hypothesis_explanation")
    op.drop_column("users", "intake_hypothesis")
