"""
Add persistent prescreening state table.

Revision ID: 003
Revises: 002
Create Date: 2026-06-02 23:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prescreening_states",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("step", sa.String(length=64), nullable=False, server_default="awaiting_therapist_name"),
        sa.Column("therapist_name", sa.String(length=255), nullable=False, server_default="Опора"),
        sa.Column("therapist_gender", sa.String(length=20), nullable=False, server_default="female"),
        sa.Column("patient_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("patient_age", sa.Integer(), nullable=True),
        sa.Column("patient_sex", sa.String(length=20), nullable=False, server_default="prefer_not_to_say"),
        sa.Column("address_mode", sa.String(length=20), nullable=False, server_default="formal"),
        sa.Column("selected_styles", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("is_edit_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["identity.accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
        schema="profile",
    )


def downgrade() -> None:
    op.drop_table("prescreening_states", schema="profile")

