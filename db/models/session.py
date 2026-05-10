"""
Therapy session model for Opora.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .decision import DecisionLog
    from .message import Message
    from .user import User


class TherapySession(Base, TimestampMixin):
    """A therapy session between user and therapist agent."""
    
    __tablename__ = "therapy_sessions"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Therapy configuration
    therapy_type: Mapped[str] = mapped_column(String(255), default="unspecified therapy")
    therapy_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Session state
    dialog_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Current stage assessment (cached)
    current_stage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    flow_phase: Mapped[str] = mapped_column(String(20), default="therapy")
    intake_user_turns: Mapped[int] = mapped_column(Integer, default=0)
    intake_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    decisions: Mapped[list["DecisionLog"]] = relationship(
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<TherapySession(id={self.id}, user_id={self.user_id}, number={self.session_number})>"
