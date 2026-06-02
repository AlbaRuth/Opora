"""Sandbox patient template model."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class PatientTemplateModel(Base, TimestampMixin):
    """Reusable LLM-patient persona for sandbox auto-run."""

    __tablename__ = "patient_templates"
    __table_args__ = {"schema": "observability"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    persona: Mapped[str] = mapped_column(Text, nullable=False)
    presenting_problem: Mapped[str] = mapped_column(Text, nullable=False)
    hidden_facts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    emotional_trajectory: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cooperation_level: Mapped[str] = mapped_column(String(100), nullable=False, default="neutral")
    safety_boundaries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    stop_conditions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    template_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
