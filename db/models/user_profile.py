"""
User Profile model for Opora.
Represents patient's personal profile and preferences.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .account import Account


class UserProfile(Base, TimestampMixin):
    """Patient's personal profile and display preferences."""

    __tablename__ = "user_profiles"
    __table_args__ = {"schema": "profile"}

    # Primary key - same as account (1:1 relationship)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("identity.accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Display info
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # NEW: Patient sex (gender) - мужской/женский/не хочу указывать
    sex: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Patient sex: male, female, prefer_not_to_say",
    )

    # NEW: Address mode - how to address the user (ты/вы)
    address_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="formal",
        comment="Address mode: formal (вы) or informal (ты)",
    )

    # Legacy fields for migration compatibility
    legacy_pseudonym: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, name="patient_pseudonym"
    )
    legacy_age_note: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, name="patient_age_legacy"
    )

    # Profile completion tracking
    profile_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship
    account: Mapped["Account"] = relationship(
        back_populates="user_profile",
        lazy="selectin",
        single_parent=True,
    )

    @property
    def is_profile_complete(self) -> bool:
        """Check if user has completed profile setup."""
        return self.profile_completed_at is not None

    @property
    def effective_display_name(self) -> str:
        """Get effective display name (fallback chain)."""
        return (
            self.display_name
            or self.legacy_pseudonym
            or (self.account.first_name if self.account else None)
            or "Пациент"
        )

    @property
    def effective_age(self) -> str:
        """Get effective age as string."""
        if self.age is not None:
            return str(self.age)
        return self.legacy_age_note or ""

    @property
    def sex_display(self) -> str:
        """Get human-readable sex display."""
        mapping = {
            "male": "Мужской",
            "female": "Женский",
            "prefer_not_to_say": "Не указан",
        }
        return mapping.get(self.sex, "Не указан")

    @property
    def address_mode_display(self) -> str:
        """Get human-readable address mode display."""
        mapping = {
            "formal": "На 'Вы'",
            "informal": "На 'Ты'",
        }
        return mapping.get(self.address_mode, "На 'Вы'")

    def __repr__(self) -> str:
        return f"<UserProfile(account_id={self.account_id}, display_name={self.display_name})>"
