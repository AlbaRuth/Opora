"""
Clinical Profile repository for Opora.
Handles clinical.clinical_profiles operations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import ClinicalProfile


class ClinicalProfileRepository:
    """Repository for ClinicalProfile operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_account_id(self, account_id: int) -> ClinicalProfile | None:
        """Get clinical profile by account ID."""
        result = await self.session.execute(
            select(ClinicalProfile).where(ClinicalProfile.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def update_clinical_data(
        self,
        account_id: int,
        mental_health_history: str | None = None,
        physical_health_history: str | None = None,
        current_problems: str | None = None,
        intake_hypothesis: str | None = None,
        intake_hypothesis_explanation: str | None = None,
        initial_info_insufficient: bool | None = None,
    ) -> ClinicalProfile | None:
        """Update clinical profile fields."""
        profile = await self.get_by_account_id(account_id)
        if not profile:
            return None

        if mental_health_history is not None:
            profile.mental_health_history = mental_health_history
        if physical_health_history is not None:
            profile.physical_health_history = physical_health_history
        if current_problems is not None:
            profile.current_problems = current_problems
        if intake_hypothesis is not None:
            profile.intake_hypothesis = intake_hypothesis
        if intake_hypothesis_explanation is not None:
            profile.intake_hypothesis_explanation = intake_hypothesis_explanation
        if initial_info_insufficient is not None:
            profile.initial_info_insufficient = initial_info_insufficient

        await self.session.flush()
        return profile

    async def is_card_filled(self, account_id: int) -> bool:
        """Check if clinical card has meaningful data."""
        profile = await self.get_by_account_id(account_id)
        if not profile:
            return False
        return profile.is_card_filled()

    async def get_patient_record(self, account_id: int) -> dict[str, str] | None:
        """Get patient record dict for agent prompts."""
        profile = await self.get_by_account_id(account_id)
        if not profile:
            return None
        return profile.get_patient_record()
