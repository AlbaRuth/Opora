"""Add persisted account origin for channel separation.

Revision ID: 006
Revises: 005
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="telegram"),
        schema="identity",
    )
    op.create_index("ix_accounts_origin", "accounts", ["origin"], schema="identity")
    op.execute(
        """
        UPDATE identity.accounts AS account
        SET origin = 'sandbox'
        WHERE EXISTS (
            SELECT 1
            FROM observability.sandbox_runs AS run
            WHERE run.account_id = account.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_accounts_origin", table_name="accounts", schema="identity")
    op.drop_column("accounts", "origin", schema="identity")
