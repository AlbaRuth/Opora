"""Add observability linkage, indexes, and constraints.

Revision ID: 007
Revises: 006
Create Date: 2026-06-03

Operational retention is configured by OBSERVABILITY_RETENTION_DAYS.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("trace_id", postgresql.UUID(as_uuid=False), nullable=True),
        schema="therapy",
    )
    op.add_column(
        "decision_logs",
        sa.Column("trace_id", postgresql.UUID(as_uuid=False), nullable=True),
        schema="therapy",
    )
    op.add_column(
        "conversation_traces",
        sa.Column("parent_trace_id", postgresql.UUID(as_uuid=False), nullable=True),
        schema="observability",
    )
    op.add_column(
        "conversation_traces",
        sa.Column("total_cost_usd", sa.Numeric(12, 8), nullable=True),
        schema="observability",
    )

    op.create_index("ix_messages_trace_id", "messages", ["trace_id"], schema="therapy")
    op.create_index("ix_messages_session_number", "messages", ["session_id", "message_number"], schema="therapy")
    op.create_index("ix_decision_logs_trace_id", "decision_logs", ["trace_id"], schema="therapy")
    op.create_index(
        "ix_decision_logs_session_response",
        "decision_logs",
        ["session_id", "response_number"],
        schema="therapy",
    )
    op.create_index("ix_therapy_sessions_updated_at", "therapy_sessions", [sa.text("updated_at DESC")], schema="therapy")
    op.create_unique_constraint(
        "uq_therapy_sessions_account_session",
        "therapy_sessions",
        ["account_id", "session_number"],
        schema="therapy",
    )

    op.create_index(
        "ix_conversation_traces_session_started",
        "conversation_traces",
        ["session_id", "started_at"],
        schema="observability",
    )
    op.create_index(
        "ix_conversation_traces_started_at",
        "conversation_traces",
        [sa.text("started_at DESC")],
        schema="observability",
    )
    op.create_index(
        "ix_conversation_traces_parent_trace_id",
        "conversation_traces",
        ["parent_trace_id"],
        schema="observability",
    )
    op.create_index(
        "ix_agent_logs_trace_created",
        "agent_logs",
        ["trace_id", "created_at"],
        schema="observability",
    )
    op.create_index(
        "ix_sandbox_turns_run_turn",
        "sandbox_turns",
        ["run_id", "turn_number"],
        schema="observability",
    )
    op.create_unique_constraint(
        "uq_sandbox_turns_run_turn",
        "sandbox_turns",
        ["run_id", "turn_number"],
        schema="observability",
    )
    op.create_unique_constraint(
        "uq_patient_templates_name_version",
        "patient_templates",
        ["name", "version"],
        schema="observability",
    )
    op.create_foreign_key(
        "fk_sandbox_turns_trace",
        "sandbox_turns",
        "conversation_traces",
        ["trace_id"],
        ["trace_id"],
        source_schema="observability",
        referent_schema="observability",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_sandbox_turns_trace", "sandbox_turns", schema="observability", type_="foreignkey")
    op.drop_constraint("uq_patient_templates_name_version", "patient_templates", schema="observability", type_="unique")
    op.drop_constraint("uq_sandbox_turns_run_turn", "sandbox_turns", schema="observability", type_="unique")
    op.drop_index("ix_sandbox_turns_run_turn", table_name="sandbox_turns", schema="observability")
    op.drop_index("ix_agent_logs_trace_created", table_name="agent_logs", schema="observability")
    op.drop_index("ix_conversation_traces_parent_trace_id", table_name="conversation_traces", schema="observability")
    op.drop_index("ix_conversation_traces_started_at", table_name="conversation_traces", schema="observability")
    op.drop_index("ix_conversation_traces_session_started", table_name="conversation_traces", schema="observability")

    op.drop_constraint("uq_therapy_sessions_account_session", "therapy_sessions", schema="therapy", type_="unique")
    op.drop_index("ix_therapy_sessions_updated_at", table_name="therapy_sessions", schema="therapy")
    op.drop_index("ix_decision_logs_session_response", table_name="decision_logs", schema="therapy")
    op.drop_index("ix_decision_logs_trace_id", table_name="decision_logs", schema="therapy")
    op.drop_index("ix_messages_session_number", table_name="messages", schema="therapy")
    op.drop_index("ix_messages_trace_id", table_name="messages", schema="therapy")

    op.drop_column("conversation_traces", "total_cost_usd", schema="observability")
    op.drop_column("conversation_traces", "parent_trace_id", schema="observability")
    op.drop_column("decision_logs", "trace_id", schema="therapy")
    op.drop_column("messages", "trace_id", schema="therapy")
