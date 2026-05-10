"""
User repository for Opora.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)
    
    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def create_from_telegram(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> User:
        """Create new user from Telegram data."""
        return await self.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )
    
    async def update_medical_record(
        self,
        user_id: int,
        pseudonym: str | None = None,
        age: str | None = None,
        mental_health: str | None = None,
        physical_health: str | None = None,
        problems: str | None = None,
    ) -> User | None:
        """Update user's medical record information."""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        return await self.update(
            user,
            patient_pseudonym=pseudonym,
            patient_age_legacy=age,
            mental_health_history=mental_health,
            physical_health_history=physical_health,
            current_problems=problems,
        )

    async def update_patient_card(
        self,
        user_id: int,
        mental_health: str | None = None,
        physical_health: str | None = None,
        problems: str | None = None,
        intake_hypothesis: str | None = None,
        intake_hypothesis_explanation: str | None = None,
    ) -> User | None:
        """Update normalized patient card fields used by intake and summary."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        update_data: dict = {}
        if mental_health is not None:
            update_data["mental_health_history"] = mental_health
        if physical_health is not None:
            update_data["physical_health_history"] = physical_health
        if problems is not None:
            update_data["current_problems"] = problems
        if intake_hypothesis is not None:
            update_data["intake_hypothesis"] = intake_hypothesis
        if intake_hypothesis_explanation is not None:
            update_data["intake_hypothesis_explanation"] = intake_hypothesis_explanation

        if not update_data:
            return user

        return await self.update(user, **update_data)
    
    async def update_prescreening_profile(
        self,
        user_id: int,
        therapist_name: str | None = None,
        therapist_gender: str | None = None,
        patient_display_name: str | None = None,
        patient_age: int | None = None,
        therapist_traits: list[str] | None = None,
        mark_complete: bool = False,
    ) -> User | None:
        """Update user's prescreening profile."""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        update_data: dict = {}
        if therapist_name is not None:
            update_data["therapist_name"] = therapist_name
        if therapist_gender is not None:
            update_data["therapist_gender"] = therapist_gender
        if patient_display_name is not None:
            update_data["patient_display_name"] = patient_display_name
        if patient_age is not None:
            update_data["patient_age"] = patient_age
        if therapist_traits is not None:
            update_data["therapist_traits"] = therapist_traits
        if mark_complete:
            update_data["prescreening_completed_at"] = datetime.utcnow()
        
        if not update_data:
            return user
        
        return await self.update(user, **update_data)
    
    async def is_prescreening_complete(self, user_id: int) -> bool:
        """Check if user has completed prescreening."""
        user = await self.get_by_id(user_id)
        if not user:
            return False
        return user.is_prescreening_complete
    
    async def get_profile(self, user_id: int) -> dict | None:
        """Get user's prescreening profile and patient record."""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        return {
            "prescreening_complete": user.is_prescreening_complete,
            "therapist_profile": user.get_therapist_profile(),
            "patient_record": user.get_patient_record(),
        }
