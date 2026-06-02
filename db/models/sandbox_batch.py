"""Sandbox batch run model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SandboxBatch(Base, TimestampMixin):
    """A group of sandbox runs started as one automated evaluation batch."""

    __tablename__ = "sandbox_batches"
    __table_args__ = {"schema": "observability"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Sandbox batch")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running", index=True)
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    parallelism: Mapped[int] = mapped_column(Integer, nullable=False)
    max_turns_per_run: Mapped[int] = mapped_column(Integer, nullable=False)
    model_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    batch_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
