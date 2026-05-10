"""
Initial schema baseline.

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import func

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("language_code", sa.String(10), nullable=True),
        # Medical record fields
        sa.Column("patient_pseudonym", sa.String(255), nullable=True),
        sa.Column("patient_age_legacy", sa.String(50), nullable=True),
        sa.Column("mental_health_history", sa.Text(), nullable=True),
        sa.Column("physical_health_history", sa.Text(), nullable=True),
        sa.Column("current_problems", sa.Text(), nullable=True),
        sa.Column("intake_hypothesis", sa.Text(), nullable=True),
        sa.Column("intake_hypothesis_explanation", sa.Text(), nullable=True),
        # Prescreening fields
        sa.Column("therapist_name", sa.String(255), nullable=True),
        sa.Column("therapist_gender", sa.String(20), nullable=True),
        sa.Column("patient_display_name", sa.String(255), nullable=True),
        sa.Column("patient_age", sa.Integer(), nullable=True),
        sa.Column("therapist_traits", sa.JSON(), nullable=True),
        sa.Column("prescreening_completed_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    # Create therapy_sessions table
    op.create_table(
        "therapy_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False),
        sa.Column("therapy_type", sa.String(255), server_default="unspecified therapy", nullable=False),
        sa.Column("therapy_reason", sa.Text(), nullable=True),
        sa.Column("dialog_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_stage", sa.Text(), nullable=True),
        sa.Column("flow_phase", sa.String(20), server_default="therapy", nullable=False),
        sa.Column("intake_user_turns", sa.Integer(), server_default="0", nullable=False),
        sa.Column("intake_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_therapy_sessions_user_id", "therapy_sessions", ["user_id"])

    # Create messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_number", sa.BigInteger(), nullable=False),
        sa.Column("primary_emotion", sa.String(50), nullable=True),
        sa.Column("emotional_intensity", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["therapy_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])

    # Create decision_logs table
    op.create_table(
        "decision_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("response_number", sa.Integer(), nullable=False),
        sa.Column("memory_invoke_result", sa.Text(), nullable=True),
        sa.Column("is_rejecting", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("current_therapy", sa.String(255), server_default="unspecified therapy", nullable=False),
        sa.Column("current_stage", sa.Text(), nullable=True),
        sa.Column("primary_emotion", sa.String(50), nullable=True),
        sa.Column("emotional_intensity", sa.Float(), nullable=True),
        sa.Column("response_strategy", sa.String(255), nullable=True),
        sa.Column("strategy_description", sa.Text(), nullable=True),
        sa.Column("patient_attitude", sa.String(50), nullable=True),
        sa.Column("decision_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["therapy_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_decision_logs_session_id", "decision_logs", ["session_id"])

    # Create agent_logs table
    op.create_table(
        "agent_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("task_name", sa.String(100), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("temperature", sa.Float(), server_default="0.7", nullable=False),
        sa.Column("max_tokens", sa.Integer(), server_default="150", nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("langfuse_trace_id", sa.String(255), nullable=True),
        sa.Column("langfuse_generation_id", sa.String(255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["therapy_sessions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_agent_logs_user_id", "agent_logs", ["user_id"])
    op.create_index("ix_agent_logs_session_id", "agent_logs", ["session_id"])
    op.create_index("ix_agent_logs_agent_type", "agent_logs", ["agent_type"])
    op.create_index("ix_agent_logs_task_name", "agent_logs", ["task_name"])
    op.create_index("ix_agent_logs_langfuse_trace_id", "agent_logs", ["langfuse_trace_id"])


def downgrade() -> None:
    # Drop tables in reverse order of creation
    op.drop_table("agent_logs")
    op.drop_table("decision_logs")
    op.drop_table("messages")
    op.drop_table("therapy_sessions")
    op.drop_table("users")
