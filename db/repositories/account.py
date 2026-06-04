"""
Account repository for Opora.
Handles identity schema operations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from db.models import Account, ClinicalProfile, TherapistPreference, UserProfile
from .base import BaseRepository


class AccountRepository(BaseRepository[Account]):
    """Repository for Account (identity) operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Account)

    async def get_by_telegram_id(self, telegram_id: int) -> Account | None:
        """Get account by Telegram ID with all related profiles."""
        result = await self.session.execute(
            select(Account)
            .where(Account.telegram_id == telegram_id)
            .options(
                selectinload(Account.user_profile),
                selectinload(Account.therapist_preference),
                selectinload(Account.clinical_profile),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_profiles(self, account_id: int) -> Account | None:
        """Get account by ID with all related profiles loaded."""
        result = await self.session.execute(
            select(Account)
            .where(Account.id == account_id)
            .options(
                selectinload(Account.user_profile),
                selectinload(Account.therapist_preference),
                selectinload(Account.clinical_profile),
            )
        )
        return result.scalar_one_or_none()

    async def create_from_telegram(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> Account:
        """Create new account from Telegram data with empty profiles."""
        # Create account
        account = await self.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )

        # Create associated empty profiles
        user_profile = UserProfile(account_id=account.id)
        therapist_pref = TherapistPreference(account_id=account.id)
        clinical_profile = ClinicalProfile(account_id=account.id)

        self.session.add_all([user_profile, therapist_pref, clinical_profile])
        await self.session.flush()

        # Attach to account for immediate use
        account.user_profile = user_profile
        account.therapist_preference = therapist_pref
        account.clinical_profile = clinical_profile

        return account

    async def delete_by_telegram_id(self, telegram_id: int) -> bool:
        """Delete account by Telegram ID with all cascaded data.
        
        Returns True if account was found and deleted, False otherwise.
        All related data (profiles, sessions, messages, logs) is deleted
        via CASCADE constraints.
        """
        account = await self.get_by_telegram_id(telegram_id)
        if not account:
            return False
        
        await self.delete(account)
        return True
