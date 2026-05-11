"""
Intake State model for Opora.
Tracks intake workflow state separately from core session data.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .therapy_session import TherapySession


class IntakeState(Base, TimestampMixin):
    """Intake workflow state for a therapy session."""

    __tablename__ = "intake_states"
    __table_args__ = {"schema": "therapy"}

    # Primary key - same as session (1:1 relationship)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("therapy.therapy_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Flow phase tracking
    flow_phase: Mapped[str] = mapped_column(
        String(20), nullable=False, default="prescreening"
    )

    # Intake progress tracking
    user_turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship
    session: Mapped["TherapySession"] = relationship(
        back_populates="intake_state",
        lazy="selectin",
        single_parent=True,
    )

    @property
    def is_intake_completed(self) -> bool:
        """Check if intake workflow is completed."""
        return self.completed_at is not None

    def __repr__(self) -> str:
        return f"<IntakeState(session_id={self.session_id}, phase={self.flow_phase}, completed={self.is_intake_completed})>"
