"""
Decision log model for agent decisions.
"""

from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class DecisionLog(Base, TimestampMixin):
    """Log of agent decisions during therapy session."""
    
    __tablename__ = "decision_logs"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("therapy_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    response_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Decision data (denormalized for quick access)
    memory_invoke_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_rejecting: Mapped[bool] = mapped_column(default=False)
    current_therapy: Mapped[str] = mapped_column(String(255), default="unspecified therapy")
    current_stage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_emotion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    emotional_intensity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    response_strategy: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    strategy_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    patient_attitude: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Full decision snapshot
    decision_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    session: Mapped["TherapySession"] = relationship(back_populates="decisions")
    
    def __repr__(self) -> str:
        return f"<DecisionLog(id={self.id}, session_id={self.session_id}, response_num={self.response_number})>"
