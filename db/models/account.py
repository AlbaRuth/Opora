"""
Account (Identity) model for Opora.
Represents Telegram user identity - the root entity for all user data.
"""

from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .agent_log import AgentLog
    from .clinical_profile import ClinicalProfile
    from .prescreening_state import PrescreeningState
    from .therapist_preference import TherapistPreference
    from .therapy_session import TherapySession
    from .user_profile import UserProfile


class Account(Base, TimestampMixin):
    """Root identity entity for Telegram user."""

    __tablename__ = "accounts"
    __table_args__ = {"schema": "identity"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Relationships - one-to-one with profile entities
    user_profile: Mapped[Optional["UserProfile"]] = relationship(
        back_populates="account",
        lazy="selectin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    therapist_preference: Mapped[Optional["TherapistPreference"]] = relationship(
        back_populates="account",
        lazy="selectin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    clinical_profile: Mapped[Optional["ClinicalProfile"]] = relationship(
        back_populates="account",
        lazy="selectin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    prescreening_state: Mapped[Optional["PrescreeningState"]] = relationship(
        back_populates="account",
        lazy="selectin",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Relationships - one-to-many
    therapy_sessions: Mapped[list["TherapySession"]] = relationship(
        back_populates="account",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    agent_logs: Mapped[list["AgentLog"]] = relationship(
        back_populates="account",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"
