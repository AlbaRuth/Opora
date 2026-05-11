"""
User Profile repository for Opora.
Handles profile.user_profiles operations.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import UserProfile


class UserProfileRepository:
    """Repository for UserProfile operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_account_id(self, account_id: int) -> UserProfile | None:
        """Get user profile by account ID."""
        result = await self.session.execute(
            select(UserProfile).where(UserProfile.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def update_profile(
        self,
        account_id: int,
        display_name: str | None = None,
        age: int | None = None,
        sex: str | None = None,
        address_mode: str | None = None,
        mark_complete: bool = False,
    ) -> UserProfile | None:
        """Update user profile fields."""
        profile = await self.get_by_account_id(account_id)
        if not profile:
            return None

        if display_name is not None:
            profile.display_name = display_name
        if age is not None:
            profile.age = age
        if sex is not None:
            profile.sex = sex
        if address_mode is not None:
            profile.address_mode = address_mode
        if mark_complete:
            profile.profile_completed_at = datetime.utcnow()

        await self.session.flush()
        return profile

    async def update_patient_info(
        self,
        account_id: int,
        display_name: str | None = None,
        age: int | None = None,
        sex: str | None = None,
        address_mode: str | None = None,
    ) -> UserProfile | None:
        """Update patient personal info (convenience method)."""
        return await self.update_profile(
            account_id=account_id,
            display_name=display_name,
            age=age,
            sex=sex,
            address_mode=address_mode,
        )
