"""Persistent wizard state for Telegram prescreening flow."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .account import Account


class PrescreeningState(Base, TimestampMixin):
    """Durable prescreening wizard state (account-scoped)."""

    __tablename__ = "prescreening_states"
    __table_args__ = {"schema": "profile"}

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("identity.accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    step: Mapped[str] = mapped_column(String(64), nullable=False, default="awaiting_therapist_name")
    therapist_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Опора")
    therapist_gender: Mapped[str] = mapped_column(String(20), nullable=False, default="female")
    patient_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    patient_age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    patient_sex: Mapped[str] = mapped_column(String(20), nullable=False, default="prefer_not_to_say")
    address_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="formal")
    selected_styles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_edit_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["Account"] = relationship(back_populates="prescreening_state", lazy="selectin")

