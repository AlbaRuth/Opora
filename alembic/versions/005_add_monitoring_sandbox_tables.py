"""
Add monitoring trace and sandbox tables.

Revision ID: 005
Revises: 004
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_logs",
        sa.Column("trace_id", postgresql.UUID(as_uuid=False), nullable=True),
        schema="observability",
    )
    op.add_column(
        "agent_logs",
        sa.Column("turn_id", postgresql.UUID(as_uuid=False), nullable=True),
        schema="observability",
    )
    op.add_column(
        "agent_logs",
        sa.Column("channel", sa.String(length=50), nullable=True),
        schema="observability",
    )
    op.add_column(
        "agent_logs",
        sa.Column("prompt_messages", sa.JSON(), nullable=True),
        schema="observability",
    )
    op.add_column(
        "agent_logs",
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        schema="observability",
    )
    op.add_column(
        "agent_logs",
        sa.Column("cost_usd", sa.Numeric(12, 8), nullable=True),
        schema="observability",
    )
    op.add_column(
        "agent_logs",
        sa.Column("provider_metadata", sa.JSON(), nullable=True),
        schema="observability",
    )
    op.create_index("ix_agent_logs_trace_id", "agent_logs", ["trace_id"], schema="observability")
    op.create_index("ix_agent_logs_turn_id", "agent_logs", ["turn_id"], schema="observability")
    op.create_index("ix_agent_logs_channel", "agent_logs", ["channel"], schema="observability")

    op.create_table(
        "conversation_traces",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("turn_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=True),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("llm_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens_input", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens_output", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["identity.accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["therapy.therapy_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trace_id"),
        schema="observability",
    )
    op.create_index("ix_conversation_traces_trace_id", "conversation_traces", ["trace_id"], schema="observability")
    op.create_index("ix_conversation_traces_turn_id", "conversation_traces", ["turn_id"], schema="observability")
    op.create_index("ix_conversation_traces_account_id", "conversation_traces", ["account_id"], schema="observability")
    op.create_index("ix_conversation_traces_session_id", "conversation_traces", ["session_id"], schema="observability")
    op.create_index("ix_conversation_traces_channel", "conversation_traces", ["channel"], schema="observability")
    op.create_index("ix_conversation_traces_source", "conversation_traces", ["source"], schema="observability")
    op.create_index("ix_conversation_traces_status", "conversation_traces", ["status"], schema="observability")

    op.create_table(
        "patient_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("persona", sa.Text(), nullable=False),
        sa.Column("presenting_problem", sa.Text(), nullable=False),
        sa.Column("hidden_facts", sa.JSON(), nullable=False),
        sa.Column("emotional_trajectory", sa.Text(), nullable=True),
        sa.Column("cooperation_level", sa.String(length=100), nullable=False),
        sa.Column("safety_boundaries", sa.JSON(), nullable=False),
        sa.Column("max_turns", sa.Integer(), nullable=False),
        sa.Column("stop_conditions", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="observability",
    )
    op.create_index("ix_patient_templates_name", "patient_templates", ["name"], schema="observability")
    op.create_index("ix_patient_templates_is_active", "patient_templates", ["is_active"], schema="observability")

    op.create_table(
        "sandbox_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("patient_template_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("model_config", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["identity.accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["therapy.therapy_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_template_id"], ["observability.patient_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="observability",
    )
    op.create_index("ix_sandbox_runs_account_id", "sandbox_runs", ["account_id"], schema="observability")
    op.create_index("ix_sandbox_runs_session_id", "sandbox_runs", ["session_id"], schema="observability")
    op.create_index("ix_sandbox_runs_patient_template_id", "sandbox_runs", ["patient_template_id"], schema="observability")
    op.create_index("ix_sandbox_runs_status", "sandbox_runs", ["status"], schema="observability")

    op.create_table(
        "sandbox_turns",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("patient_message", sa.Text(), nullable=False),
        sa.Column("assistant_message", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["observability.sandbox_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="observability",
    )
    op.create_index("ix_sandbox_turns_run_id", "sandbox_turns", ["run_id"], schema="observability")
    op.create_index("ix_sandbox_turns_trace_id", "sandbox_turns", ["trace_id"], schema="observability")


def downgrade() -> None:
    op.drop_index("ix_sandbox_turns_trace_id", table_name="sandbox_turns", schema="observability")
    op.drop_index("ix_sandbox_turns_run_id", table_name="sandbox_turns", schema="observability")
    op.drop_table("sandbox_turns", schema="observability")

    op.drop_index("ix_sandbox_runs_status", table_name="sandbox_runs", schema="observability")
    op.drop_index("ix_sandbox_runs_patient_template_id", table_name="sandbox_runs", schema="observability")
    op.drop_index("ix_sandbox_runs_session_id", table_name="sandbox_runs", schema="observability")
    op.drop_index("ix_sandbox_runs_account_id", table_name="sandbox_runs", schema="observability")
    op.drop_table("sandbox_runs", schema="observability")

    op.drop_index("ix_patient_templates_is_active", table_name="patient_templates", schema="observability")
    op.drop_index("ix_patient_templates_name", table_name="patient_templates", schema="observability")
    op.drop_table("patient_templates", schema="observability")

    op.drop_index("ix_conversation_traces_status", table_name="conversation_traces", schema="observability")
    op.drop_index("ix_conversation_traces_source", table_name="conversation_traces", schema="observability")
    op.drop_index("ix_conversation_traces_channel", table_name="conversation_traces", schema="observability")
    op.drop_index("ix_conversation_traces_session_id", table_name="conversation_traces", schema="observability")
    op.drop_index("ix_conversation_traces_account_id", table_name="conversation_traces", schema="observability")
    op.drop_index("ix_conversation_traces_turn_id", table_name="conversation_traces", schema="observability")
    op.drop_index("ix_conversation_traces_trace_id", table_name="conversation_traces", schema="observability")
    op.drop_table("conversation_traces", schema="observability")

    op.drop_index("ix_agent_logs_channel", table_name="agent_logs", schema="observability")
    op.drop_index("ix_agent_logs_turn_id", table_name="agent_logs", schema="observability")
    op.drop_index("ix_agent_logs_trace_id", table_name="agent_logs", schema="observability")
    op.drop_column("agent_logs", "provider_metadata", schema="observability")
    op.drop_column("agent_logs", "cost_usd", schema="observability")
    op.drop_column("agent_logs", "reasoning_summary", schema="observability")
    op.drop_column("agent_logs", "prompt_messages", schema="observability")
    op.drop_column("agent_logs", "channel", schema="observability")
    op.drop_column("agent_logs", "turn_id", schema="observability")
    op.drop_column("agent_logs", "trace_id", schema="observability")
