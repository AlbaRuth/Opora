"""Sandbox run model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SandboxRun(Base, TimestampMixin):
    """A synthetic conversation run driven from the monitor UI."""

    __tablename__ = "sandbox_runs"
    __table_args__ = {"schema": "observability"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("identity.accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("therapy.therapy_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("observability.patient_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("observability.sandbox_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Sandbox run")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    model_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    run_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
