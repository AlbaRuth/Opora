"""
User (Telegram) model for Opora.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Telegram user interacting with Opora bot."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    
    # Medical record summary (denormalized for quick access)
    patient_pseudonym: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    patient_age_legacy: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mental_health_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    physical_health_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_problems: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intake_hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intake_hypothesis_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Prescreening profile fields
    therapist_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default="Опора"
    )
    therapist_gender: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default="female"
    )
    patient_display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    patient_age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    therapist_traits: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True, default=list)
    prescreening_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Relationships
    sessions: Mapped[list["TherapySession"]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    agent_logs: Mapped[list["AgentLog"]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.therapist_name is None:
            self.therapist_name = "Опора"
        if self.therapist_gender is None:
            self.therapist_gender = "female"
        if self.therapist_traits is None:
            self.therapist_traits = []
    
    @property
    def is_prescreening_complete(self) -> bool:
        """Check if user has completed prescreening."""
        return self.prescreening_completed_at is not None
    
    def get_patient_record(self) -> dict[str, str]:
        """Build patient record dict for agent prompts."""
        return {
            "patient_pseudonym": self.patient_display_name or self.patient_pseudonym or "",
            "patient_age": str(self.patient_age) if self.patient_age is not None else self.patient_age_legacy or "",
            "mental_health_history": self.mental_health_history or "",
            "physical_health_history": self.physical_health_history or "",
            "current_problems": self.current_problems or "",
            "intake_hypothesis": self.intake_hypothesis or "",
            "intake_hypothesis_explanation": self.intake_hypothesis_explanation or "",
        }
    
    def get_therapist_profile(self) -> dict[str, any]:
        """Get therapist persona configuration for prompts."""
        return {
            "name": self.therapist_name or "Опора",
            "gender": self.therapist_gender or "female",
            "traits": self.therapist_traits or [],
        }
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"
