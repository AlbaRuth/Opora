"""
Therapist Preference model for Opora.
Represents user's preferred therapist persona configuration.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .account import Account


class TherapistPreference(Base, TimestampMixin):
    """User's preferred therapist persona and prescreening completion."""

    __tablename__ = "therapist_preferences"
    __table_args__ = {"schema": "profile"}

    # Primary key - same as account (1:1 relationship)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("identity.accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Therapist persona configuration
    therapist_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Опора"
    )
    therapist_gender: Mapped[str] = mapped_column(
        String(20), nullable=False, default="female"
    )
    therapist_traits: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True, default=list
    )

    # Prescreening completion tracking
    prescreening_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship
    account: Mapped["Account"] = relationship(
        back_populates="therapist_preference",
        lazy="selectin",
        single_parent=True,
    )

    @property
    def is_prescreening_complete(self) -> bool:
        """Check if user has completed prescreening."""
        return self.prescreening_completed_at is not None

    def get_therapist_profile(self) -> dict:
        """Get therapist persona configuration for prompts (NEW: returns styles)."""
        return {
            "name": self.therapist_name,
            "gender": self.therapist_gender,
            "styles": self.therapist_traits or [],  # NEW: traits field stores styles
        }

    def __repr__(self) -> str:
        return f"<TherapistPreference(account_id={self.account_id}, name={self.therapist_name})>"
