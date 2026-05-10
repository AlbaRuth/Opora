"""
Add prescreening profile fields to users table.

Revision ID: 002
Revises: 001
Create Date: 2026-01-02 00:00:00.000000

For existing databases created before prescreening feature.
All these fields are now included in the baseline schema (001),
but this revision ensures safe migration path for older databases.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add prescreening columns to users table (if not already present)
    # Using IF NOT EXISTS for safety on existing databases
    columns_to_add = [
        ("therapist_name", sa.String(255), "Опора"),
        ("therapist_gender", sa.String(20), "female"),
        ("patient_display_name", sa.String(255), None),
        ("patient_age", sa.Integer(), None),
        ("therapist_traits", sa.JSON(), None),
        ("prescreening_completed_at", sa.DateTime(timezone=True), None),
    ]
    
    for col_name, col_type, default in columns_to_add:
        # Check if column exists
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
            kwargs = {"nullable": True}
            if default is not None:
                kwargs["server_default"] = sa.text(f"'{default}'")
            op.add_column("users", sa.Column(col_name, col_type, **kwargs))

    # Rename patient_age to patient_age_legacy if old column exists
    conn = op.get_bind()
    result = conn.execute(
        sa.text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'patient_age'
        """)
    )
    
    if result.scalar_one_or_none() is not None:
        # Check if patient_age_legacy already exists
        result_legacy = conn.execute(
            sa.text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'patient_age_legacy'
            """)
        )
        
        if result_legacy.scalar_one_or_none() is None:
            op.alter_column("users", "patient_age", new_column_name="patient_age_legacy")


def downgrade() -> None:
    # Remove prescreening columns
    columns_to_remove = [
        "therapist_name",
        "therapist_gender",
        "patient_display_name",
        "patient_age",
        "therapist_traits",
        "prescreening_completed_at",
    ]
    
    for col_name in columns_to_remove:
        op.drop_column("users", col_name)
    
    # Rename back if needed (this is destructive, use with caution)
    # op.alter_column("users", "patient_age_legacy", new_column_name="patient_age")
