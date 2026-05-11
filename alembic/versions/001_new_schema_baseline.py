"""
New schema baseline with normalized tables across schemas.

Revision ID: 001
Revises:
Create Date: 2026-05-10 00:00:00.000000

This revision creates a completely new schema structure:
- identity.accounts - root entity for Telegram users
- profile.user_profiles - patient personal info (NEW: sex, address_mode)
- profile.therapist_preferences - therapist persona config
- clinical.clinical_profiles - medical/clinical data
- therapy.therapy_sessions - session headers
- therapy.intake_states - intake workflow state (separate from sessions)
- therapy.messages - session messages
- therapy.decision_logs - agent decisions
- observability.agent_logs - LLM call observability
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
    # Create schemas
    op.execute("CREATE SCHEMA IF NOT EXISTS identity")
    op.execute("CREATE SCHEMA IF NOT EXISTS profile")
    op.execute("CREATE SCHEMA IF NOT EXISTS clinical")
    op.execute("CREATE SCHEMA IF NOT EXISTS therapy")
    op.execute("CREATE SCHEMA IF NOT EXISTS observability")

    # ==================== IDENTITY SCHEMA ====================
    # Create accounts table (root entity)
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("language_code", sa.String(10), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="identity",
    )
    op.create_index(
        "ix_accounts_telegram_id",
        "accounts",
        ["telegram_id"],
        unique=True,
        schema="identity",
    )

    # ==================== PROFILE SCHEMA ====================
    # Create user_profiles table (NEW: sex, address_mode fields)
    op.create_table(
        "user_profiles",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        # NEW: Patient sex (gender) - male/female/prefer_not_to_say
        sa.Column(
            "sex",
            sa.String(20),
            nullable=True,
            comment="Patient sex: male, female, prefer_not_to_say",
        ),
        # NEW: Address mode - formal (вы) or informal (ты)
        sa.Column(
            "address_mode",
            sa.String(20),
            server_default="formal",
            nullable=False,
            comment="Address mode: formal (вы) or informal (ты)",
        ),
        # Legacy fields for data migration
        sa.Column("patient_pseudonym", sa.String(255), nullable=True),
        sa.Column("patient_age_legacy", sa.String(50), nullable=True),
        # Completion tracking
        sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("account_id"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["identity.accounts.id"],
            ondelete="CASCADE",
        ),
        schema="profile",
    )

    # Create therapist_preferences table
    op.create_table(
        "therapist_preferences",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("therapist_name", sa.String(255), server_default="Опора", nullable=False),
        sa.Column("therapist_gender", sa.String(20), server_default="female", nullable=False),
        sa.Column("therapist_traits", sa.JSON(), nullable=True),
        sa.Column("prescreening_completed_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("account_id"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["identity.accounts.id"],
            ondelete="CASCADE",
        ),
        schema="profile",
    )

    # ==================== CLINICAL SCHEMA ====================
    # Create clinical_profiles table
    op.create_table(
        "clinical_profiles",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("mental_health_history", sa.Text(), nullable=True),
        sa.Column("physical_health_history", sa.Text(), nullable=True),
        sa.Column("current_problems", sa.Text(), nullable=True),
        sa.Column("intake_hypothesis", sa.Text(), nullable=True),
        sa.Column("intake_hypothesis_explanation", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("account_id"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["identity.accounts.id"],
            ondelete="CASCADE",
        ),
        schema="clinical",
    )

    # ==================== THERAPY SCHEMA ====================
    # Create therapy_sessions table
    op.create_table(
        "therapy_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False),
        sa.Column("therapy_type", sa.String(255), server_default="unspecified therapy", nullable=False),
        sa.Column("therapy_reason", sa.Text(), nullable=True),
        sa.Column("dialog_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_stage", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["identity.accounts.id"],
            ondelete="CASCADE",
        ),
        schema="therapy",
    )
    op.create_index(
        "ix_therapy_sessions_account_id",
        "therapy_sessions",
        ["account_id"],
        schema="therapy",
    )

    # Create intake_states table (NEW - separate from sessions)
    op.create_table(
        "intake_states",
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("flow_phase", sa.String(20), server_default="prescreening", nullable=False),
        sa.Column("user_turn_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["therapy.therapy_sessions.id"],
            ondelete="CASCADE",
        ),
        schema="therapy",
    )

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
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["therapy.therapy_sessions.id"],
            ondelete="CASCADE",
        ),
        schema="therapy",
    )
    op.create_index(
        "ix_messages_session_id",
        "messages",
        ["session_id"],
        schema="therapy",
    )

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
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["therapy.therapy_sessions.id"],
            ondelete="CASCADE",
        ),
        schema="therapy",
    )
    op.create_index(
        "ix_decision_logs_session_id",
        "decision_logs",
        ["session_id"],
        schema="therapy",
    )

    # ==================== OBSERVABILITY SCHEMA ====================
    # Create agent_logs table
    op.create_table(
        "agent_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
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
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["identity.accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["therapy.therapy_sessions.id"],
            ondelete="SET NULL",
        ),
        schema="observability",
    )
    op.create_index(
        "ix_agent_logs_account_id",
        "agent_logs",
        ["account_id"],
        schema="observability",
    )
    op.create_index(
        "ix_agent_logs_session_id",
        "agent_logs",
        ["session_id"],
        schema="observability",
    )
    op.create_index(
        "ix_agent_logs_agent_type",
        "agent_logs",
        ["agent_type"],
        schema="observability",
    )
    op.create_index(
        "ix_agent_logs_task_name",
        "agent_logs",
        ["task_name"],
        schema="observability",
    )
    op.create_index(
        "ix_agent_logs_langfuse_trace_id",
        "agent_logs",
        ["langfuse_trace_id"],
        schema="observability",
    )


def downgrade() -> None:
    # Drop tables in reverse order (respecting FK constraints)
    op.drop_table("agent_logs", schema="observability")
    op.drop_table("decision_logs", schema="therapy")
    op.drop_table("messages", schema="therapy")
    op.drop_table("intake_states", schema="therapy")
    op.drop_table("therapy_sessions", schema="therapy")
    op.drop_table("clinical_profiles", schema="clinical")
    op.drop_table("therapist_preferences", schema="profile")
    op.drop_table("user_profiles", schema="profile")
    op.drop_table("accounts", schema="identity")

    # Drop schemas
    op.execute("DROP SCHEMA IF EXISTS observability CASCADE")
    op.execute("DROP SCHEMA IF EXISTS therapy CASCADE")
    op.execute("DROP SCHEMA IF EXISTS clinical CASCADE")
    op.execute("DROP SCHEMA IF EXISTS profile CASCADE")
    op.execute("DROP SCHEMA IF EXISTS identity CASCADE")
