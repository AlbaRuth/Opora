"""Remove monitoring sandbox tables and multi-channel columns.

Revision ID: 009
Revises: 008
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove synthetic sandbox accounts before dropping origin column.
    op.execute(
        """
        DELETE FROM identity.accounts
        WHERE origin = 'sandbox'
           OR telegram_id >= 900000000000
        """
    )

    op.drop_index(
        "ix_conversation_traces_sandbox_run_started",
        table_name="conversation_traces",
        schema="observability",
    )
    op.drop_index(
        "ix_agent_logs_sandbox_batch_created",
        table_name="agent_logs",
        schema="observability",
    )
    op.drop_index(
        "ix_agent_logs_sandbox_run_created",
        table_name="agent_logs",
        schema="observability",
    )

    op.drop_constraint(
        "fk_conversation_traces_sandbox_batch",
        "conversation_traces",
        schema="observability",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_conversation_traces_sandbox_run",
        "conversation_traces",
        schema="observability",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_agent_logs_sandbox_batch",
        "agent_logs",
        schema="observability",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_agent_logs_sandbox_run",
        "agent_logs",
        schema="observability",
        type_="foreignkey",
    )

    op.drop_column("conversation_traces", "sandbox_batch_id", schema="observability")
    op.drop_column("conversation_traces", "sandbox_run_id", schema="observability")
    op.drop_column("agent_logs", "sandbox_batch_id", schema="observability")
    op.drop_column("agent_logs", "sandbox_run_id", schema="observability")

    op.drop_constraint(
        "fk_sandbox_turns_trace",
        "sandbox_turns",
        schema="observability",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_sandbox_turns_run_turn",
        "sandbox_turns",
        schema="observability",
        type_="unique",
    )
    op.drop_index(
        "ix_sandbox_turns_run_turn",
        table_name="sandbox_turns",
        schema="observability",
    )
    op.drop_index(
        "ix_sandbox_turns_trace_id",
        table_name="sandbox_turns",
        schema="observability",
    )
    op.drop_index(
        "ix_sandbox_turns_run_id",
        table_name="sandbox_turns",
        schema="observability",
    )
    op.drop_table("sandbox_turns", schema="observability")

    op.drop_index(
        "ix_sandbox_runs_batch_id",
        table_name="sandbox_runs",
        schema="observability",
    )
    op.drop_constraint(
        "fk_sandbox_runs_batch",
        "sandbox_runs",
        schema="observability",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_sandbox_runs_status",
        table_name="sandbox_runs",
        schema="observability",
    )
    op.drop_index(
        "ix_sandbox_runs_patient_template_id",
        table_name="sandbox_runs",
        schema="observability",
    )
    op.drop_index(
        "ix_sandbox_runs_session_id",
        table_name="sandbox_runs",
        schema="observability",
    )
    op.drop_index(
        "ix_sandbox_runs_account_id",
        table_name="sandbox_runs",
        schema="observability",
    )
    op.drop_table("sandbox_runs", schema="observability")

    op.drop_index(
        "ix_sandbox_batches_status",
        table_name="sandbox_batches",
        schema="observability",
    )
    op.drop_table("sandbox_batches", schema="observability")

    op.drop_index(
        "ix_patient_templates_is_active",
        table_name="patient_templates",
        schema="observability",
    )
    op.drop_index(
        "ix_patient_templates_name",
        table_name="patient_templates",
        schema="observability",
    )
    op.drop_table("patient_templates", schema="observability")

    op.drop_index(
        "ix_messages_channel_session_number",
        table_name="messages",
        schema="therapy",
    )
    op.drop_constraint(
        "ck_messages_channel_known",
        "messages",
        schema="therapy",
        type_="check",
    )
    op.drop_column("messages", "channel", schema="therapy")

    op.drop_index("ix_accounts_origin", table_name="accounts", schema="identity")
    op.drop_column("accounts", "origin", schema="identity")


def downgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="telegram"),
        schema="identity",
    )
    op.create_index("ix_accounts_origin", "accounts", ["origin"], schema="identity")
    op.alter_column("accounts", "origin", server_default=None, schema="identity")

    op.add_column(
        "messages",
        sa.Column("channel", sa.String(length=50), nullable=True),
        schema="therapy",
    )
    op.execute("UPDATE therapy.messages SET channel = 'telegram' WHERE channel IS NULL")
    op.alter_column("messages", "channel", nullable=False, schema="therapy")
    op.create_check_constraint(
        "ck_messages_channel_known",
        "messages",
        "channel IN ('telegram', 'sandbox')",
        schema="therapy",
    )
    op.create_index(
        "ix_messages_channel_session_number",
        "messages",
        ["channel", "session_id", "message_number"],
        schema="therapy",
    )

    op.create_table(
        "patient_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("profile_data", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="observability",
    )
    op.create_index(
        "ix_patient_templates_name",
        "patient_templates",
        ["name"],
        schema="observability",
    )
    op.create_index(
        "ix_patient_templates_is_active",
        "patient_templates",
        ["is_active"],
        schema="observability",
    )

    op.create_table(
        "sandbox_batches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("parallelism", sa.Integer(), nullable=False),
        sa.Column("max_turns_per_run", sa.Integer(), nullable=False),
        sa.Column("model_config", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="observability",
    )
    op.create_index(
        "ix_sandbox_batches_status",
        "sandbox_batches",
        ["status"],
        schema="observability",
    )

    op.create_table(
        "sandbox_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("patient_template_id", sa.BigInteger(), nullable=True),
        sa.Column("batch_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("model_config", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["identity.accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["therapy.therapy_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["patient_template_id"],
            ["observability.patient_templates.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["observability.sandbox_batches.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="observability",
    )
    op.create_index(
        "ix_sandbox_runs_account_id",
        "sandbox_runs",
        ["account_id"],
        schema="observability",
    )
    op.create_index(
        "ix_sandbox_runs_session_id",
        "sandbox_runs",
        ["session_id"],
        schema="observability",
    )
    op.create_index(
        "ix_sandbox_runs_patient_template_id",
        "sandbox_runs",
        ["patient_template_id"],
        schema="observability",
    )
    op.create_index(
        "ix_sandbox_runs_status",
        "sandbox_runs",
        ["status"],
        schema="observability",
    )
    op.create_index(
        "ix_sandbox_runs_batch_id",
        "sandbox_runs",
        ["batch_id"],
        schema="observability",
    )

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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["observability.sandbox_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="observability",
    )
    op.create_index(
        "ix_sandbox_turns_run_id",
        "sandbox_turns",
        ["run_id"],
        schema="observability",
    )
    op.create_index(
        "ix_sandbox_turns_trace_id",
        "sandbox_turns",
        ["trace_id"],
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

    op.add_column(
        "agent_logs",
        sa.Column("sandbox_run_id", sa.BigInteger(), nullable=True),
        schema="observability",
    )
    op.add_column(
        "agent_logs",
        sa.Column("sandbox_batch_id", sa.BigInteger(), nullable=True),
        schema="observability",
    )
    op.add_column(
        "conversation_traces",
        sa.Column("sandbox_run_id", sa.BigInteger(), nullable=True),
        schema="observability",
    )
    op.add_column(
        "conversation_traces",
        sa.Column("sandbox_batch_id", sa.BigInteger(), nullable=True),
        schema="observability",
    )

    op.create_foreign_key(
        "fk_agent_logs_sandbox_run",
        "agent_logs",
        "sandbox_runs",
        ["sandbox_run_id"],
        ["id"],
        source_schema="observability",
        referent_schema="observability",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_agent_logs_sandbox_batch",
        "agent_logs",
        "sandbox_batches",
        ["sandbox_batch_id"],
        ["id"],
        source_schema="observability",
        referent_schema="observability",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_conversation_traces_sandbox_run",
        "conversation_traces",
        "sandbox_runs",
        ["sandbox_run_id"],
        ["id"],
        source_schema="observability",
        referent_schema="observability",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_conversation_traces_sandbox_batch",
        "conversation_traces",
        "sandbox_batches",
        ["sandbox_batch_id"],
        ["id"],
        source_schema="observability",
        referent_schema="observability",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_agent_logs_sandbox_run_created",
        "agent_logs",
        ["sandbox_run_id", "created_at"],
        schema="observability",
    )
    op.create_index(
        "ix_agent_logs_sandbox_batch_created",
        "agent_logs",
        ["sandbox_batch_id", "created_at"],
        schema="observability",
    )
    op.create_index(
        "ix_conversation_traces_sandbox_run_started",
        "conversation_traces",
        ["sandbox_run_id", "started_at"],
        schema="observability",
    )
