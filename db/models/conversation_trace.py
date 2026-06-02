"""End-to-end conversation trace model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ConversationTrace(Base, TimestampMixin):
    """One user-visible turn across service and LLM calls."""

    __tablename__ = "conversation_traces"
    __table_args__ = {"schema": "observability"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, unique=True, index=True)
    parent_trace_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    turn_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("identity.accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("therapy.therapy_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sandbox_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("observability.sandbox_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sandbox_batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("observability.sandbox_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="success", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    llm_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens_input: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens_output: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(Numeric(12, 8), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
