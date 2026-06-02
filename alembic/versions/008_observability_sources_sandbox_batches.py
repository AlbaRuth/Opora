"""Add observability provenance and sandbox batches.

Revision ID: 008
Revises: 007
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="observability",
    )
    op.create_index("ix_sandbox_batches_status", "sandbox_batches", ["status"], schema="observability")

    op.add_column(
        "sandbox_runs",
        sa.Column("batch_id", sa.BigInteger(), nullable=True),
        schema="observability",
    )
    op.create_foreign_key(
        "fk_sandbox_runs_batch",
        "sandbox_runs",
        "sandbox_batches",
        ["batch_id"],
        ["id"],
        source_schema="observability",
        referent_schema="observability",
        ondelete="SET NULL",
    )
    op.create_index("ix_sandbox_runs_batch_id", "sandbox_runs", ["batch_id"], schema="observability")

    op.add_column("messages", sa.Column("channel", sa.String(50), nullable=True), schema="therapy")
    op.execute(
        """
        UPDATE therapy.messages m
        SET channel = COALESCE(a.origin, 'telegram')
        FROM therapy.therapy_sessions ts
        JOIN identity.accounts a ON a.id = ts.account_id
        WHERE ts.id = m.session_id
        """
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

    op.add_column("agent_logs", sa.Column("source", sa.String(100), nullable=True), schema="observability")
    op.add_column("agent_logs", sa.Column("sandbox_run_id", sa.BigInteger(), nullable=True), schema="observability")
    op.add_column("agent_logs", sa.Column("sandbox_batch_id", sa.BigInteger(), nullable=True), schema="observability")
    op.add_column("agent_logs", sa.Column("prompt_messages_full", sa.JSON(), nullable=True), schema="observability")
    op.add_column("agent_logs", sa.Column("response_full", sa.Text(), nullable=True), schema="observability")
    op.add_column("agent_logs", sa.Column("prompt_truncated", sa.Boolean(), server_default="false", nullable=False), schema="observability")
    op.add_column("agent_logs", sa.Column("response_truncated", sa.Boolean(), server_default="false", nullable=False), schema="observability")

    op.add_column("conversation_traces", sa.Column("sandbox_run_id", sa.BigInteger(), nullable=True), schema="observability")
    op.add_column("conversation_traces", sa.Column("sandbox_batch_id", sa.BigInteger(), nullable=True), schema="observability")

    op.execute(
        """
        UPDATE observability.agent_logs al
        SET source = ct.source
        FROM observability.conversation_traces ct
        WHERE al.trace_id = ct.trace_id AND al.source IS NULL
        """
    )
    op.execute("UPDATE observability.agent_logs SET source = 'unknown' WHERE source IS NULL")

    op.execute(
        """
        UPDATE observability.conversation_traces ct
        SET sandbox_run_id = st.run_id
        FROM observability.sandbox_turns st
        WHERE st.trace_id = ct.trace_id
        """
    )
    op.execute(
        """
        UPDATE observability.agent_logs al
        SET sandbox_run_id = st.run_id
        FROM observability.sandbox_turns st
        WHERE st.trace_id = al.trace_id
        """
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
        "ix_agent_logs_channel_source_created",
        "agent_logs",
        ["channel", "source", "created_at"],
        schema="observability",
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
        "ix_conversation_traces_channel_source_started",
        "conversation_traces",
        ["channel", "source", "started_at"],
        schema="observability",
    )
    op.create_index(
        "ix_conversation_traces_sandbox_run_started",
        "conversation_traces",
        ["sandbox_run_id", "started_at"],
        schema="observability",
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_traces_sandbox_run_started", table_name="conversation_traces", schema="observability")
    op.drop_index("ix_conversation_traces_channel_source_started", table_name="conversation_traces", schema="observability")
    op.drop_index("ix_agent_logs_sandbox_batch_created", table_name="agent_logs", schema="observability")
    op.drop_index("ix_agent_logs_sandbox_run_created", table_name="agent_logs", schema="observability")
    op.drop_index("ix_agent_logs_channel_source_created", table_name="agent_logs", schema="observability")

    op.drop_constraint("fk_conversation_traces_sandbox_batch", "conversation_traces", schema="observability", type_="foreignkey")
    op.drop_constraint("fk_conversation_traces_sandbox_run", "conversation_traces", schema="observability", type_="foreignkey")
    op.drop_constraint("fk_agent_logs_sandbox_batch", "agent_logs", schema="observability", type_="foreignkey")
    op.drop_constraint("fk_agent_logs_sandbox_run", "agent_logs", schema="observability", type_="foreignkey")

    op.drop_column("conversation_traces", "sandbox_batch_id", schema="observability")
    op.drop_column("conversation_traces", "sandbox_run_id", schema="observability")

    op.drop_column("agent_logs", "response_truncated", schema="observability")
    op.drop_column("agent_logs", "prompt_truncated", schema="observability")
    op.drop_column("agent_logs", "response_full", schema="observability")
    op.drop_column("agent_logs", "prompt_messages_full", schema="observability")
    op.drop_column("agent_logs", "sandbox_batch_id", schema="observability")
    op.drop_column("agent_logs", "sandbox_run_id", schema="observability")
    op.drop_column("agent_logs", "source", schema="observability")

    op.drop_index("ix_messages_channel_session_number", table_name="messages", schema="therapy")
    op.drop_constraint("ck_messages_channel_known", "messages", schema="therapy", type_="check")
    op.drop_column("messages", "channel", schema="therapy")

    op.drop_index("ix_sandbox_runs_batch_id", table_name="sandbox_runs", schema="observability")
    op.drop_constraint("fk_sandbox_runs_batch", "sandbox_runs", schema="observability", type_="foreignkey")
    op.drop_column("sandbox_runs", "batch_id", schema="observability")

    op.drop_index("ix_sandbox_batches_status", table_name="sandbox_batches", schema="observability")
    op.drop_table("sandbox_batches", schema="observability")
