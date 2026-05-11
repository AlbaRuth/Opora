"""
Therapist Preference repository for Opora.
Handles profile.therapist_preferences operations.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import TherapistPreference


class TherapistPreferenceRepository:
    """Repository for TherapistPreference operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_account_id(self, account_id: int) -> TherapistPreference | None:
        """Get therapist preference by account ID."""
        result = await self.session.execute(
            select(TherapistPreference).where(TherapistPreference.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def update_preferences(
        self,
        account_id: int,
        therapist_name: str | None = None,
        therapist_gender: str | None = None,
        therapist_traits: list[str] | None = None,
        mark_complete: bool = False,
    ) -> TherapistPreference | None:
        """Update therapist preference fields."""
        pref = await self.get_by_account_id(account_id)
        if not pref:
            return None

        if therapist_name is not None:
            pref.therapist_name = therapist_name
        if therapist_gender is not None:
            pref.therapist_gender = therapist_gender
        if therapist_traits is not None:
            pref.therapist_traits = therapist_traits
        if mark_complete:
            pref.prescreening_completed_at = datetime.utcnow()

        await self.session.flush()
        return pref

    async def is_prescreening_complete(self, account_id: int) -> bool:
        """Check if prescreening is complete for account."""
        pref = await self.get_by_account_id(account_id)
        if not pref:
            return False
        return pref.is_prescreening_complete
