"""
Message model for therapy sessions.
"""

from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Message(Base, TimestampMixin):
    """A single message in a therapy session."""
    
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("therapy_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Message metadata
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "patient" or "doctor"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    # Optional emotional analysis (cached)
    primary_emotion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    emotional_intensity: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    # Relationships
    session: Mapped["TherapySession"] = relationship(back_populates="messages")
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, number={self.message_number})>"
