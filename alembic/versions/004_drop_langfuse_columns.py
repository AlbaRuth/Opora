"""
Drop Langfuse correlation columns from agent_logs.

Revision ID: 004
Revises: 003
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "ix_agent_logs_langfuse_trace_id",
        table_name="agent_logs",
        schema="observability",
    )
    op.drop_column("agent_logs", "langfuse_generation_id", schema="observability")
    op.drop_column("agent_logs", "langfuse_trace_id", schema="observability")


def downgrade() -> None:
    op.add_column(
        "agent_logs",
        sa.Column("langfuse_trace_id", sa.String(255), nullable=True),
        schema="observability",
    )
    op.add_column(
        "agent_logs",
        sa.Column("langfuse_generation_id", sa.String(255), nullable=True),
        schema="observability",
    )
    op.create_index(
        "ix_agent_logs_langfuse_trace_id",
        "agent_logs",
        ["langfuse_trace_id"],
        schema="observability",
    )
