"""Sandbox turn model."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SandboxTurn(Base, TimestampMixin):
    """One patient/assistant pair produced during a sandbox run."""

    __tablename__ = "sandbox_turns"
    __table_args__ = {"schema": "observability"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("observability.sandbox_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trace_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("observability.conversation_traces.trace_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_message: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_message: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stop_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    turn_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
