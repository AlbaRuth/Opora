"""
Clinical Profile model for Opora.
Represents patient's clinical/medical record data.
"""

from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .account import Account


class ClinicalProfile(Base, TimestampMixin):
    """Patient's clinical and medical record data."""

    __tablename__ = "clinical_profiles"
    __table_args__ = {"schema": "clinical"}

    # Primary key - same as account (1:1 relationship)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("identity.accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Medical history fields
    mental_health_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    physical_health_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_problems: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Intake hypothesis fields
    intake_hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intake_hypothesis_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Flag indicating insufficient initial information during intake
    initial_info_insufficient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship
    account: Mapped["Account"] = relationship(
        back_populates="clinical_profile",
        lazy="selectin",
        single_parent=True,
    )

    def get_patient_record(self) -> dict[str, str]:
        """Build patient record dict for agent prompts."""
        # Get user profile data through account relationship
        user_profile = self.account.user_profile if self.account else None

        return {
            "patient_pseudonym": (
                user_profile.effective_display_name if user_profile else ""
            ),
            "patient_age": (user_profile.effective_age if user_profile else ""),
            "patient_sex": (user_profile.sex or "prefer_not_to_say" if user_profile else "prefer_not_to_say"),
            "mental_health_history": self.mental_health_history or "",
            "physical_health_history": self.physical_health_history or "",
            "current_problems": self.current_problems or "",
            "intake_hypothesis": self.intake_hypothesis or "",
            "intake_hypothesis_explanation": self.intake_hypothesis_explanation or "",
            "initial_info_insufficient": "true" if self.initial_info_insufficient else "false",
        }

    def is_card_filled(self) -> bool:
        """Check if patient card has any meaningful data filled."""
        meaningful_fields = [
            self.mental_health_history,
            self.physical_health_history,
            self.current_problems,
            self.intake_hypothesis,
            self.intake_hypothesis_explanation,
        ]
        return any(field and field.strip() for field in meaningful_fields)

    def __repr__(self) -> str:
        return f"<ClinicalProfile(account_id={self.account_id}, has_data={self.is_card_filled()})>"
