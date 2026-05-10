"""
Unit tests for UserRepository with prescreening functionality.
"""

import pytest
from datetime import datetime

from db.models import User
from db.repositories import UserRepository


@pytest.mark.asyncio
class TestUserRepositoryPrescreening:
    """Test prescreening-related methods in UserRepository."""

    async def test_update_prescreening_profile(self, db_session):
        """Test updating prescreening profile fields."""
        # Create user
        user = User(
            telegram_id=12345,
            username="testuser",
        )
        db_session.add(user)
        await db_session.commit()

        # Update prescreening profile
        repo = UserRepository(db_session)
        updated = await repo.update_prescreening_profile(
            user_id=user.id,
            therapist_name="Доктор Анна",
            therapist_gender="female",
            patient_display_name="Антон",
            patient_age=30,
            therapist_traits=["calm", "empathetic"],
        )

        assert updated is not None
        assert updated.therapist_name == "Доктор Анна"
        assert updated.therapist_gender == "female"
        assert updated.patient_display_name == "Антон"
        assert updated.patient_age == 30
        assert updated.therapist_traits == ["calm", "empathetic"]
        assert updated.prescreening_completed_at is None

    async def test_update_prescreening_profile_mark_complete(self, db_session):
        """Test marking prescreening as complete."""
        # Create user
        user = User(
            telegram_id=12345,
            username="testuser",
        )
        db_session.add(user)
        await db_session.commit()

        # Mark complete
        repo = UserRepository(db_session)
        updated = await repo.update_prescreening_profile(
            user_id=user.id,
            therapist_name="Доктор Иван",
            therapist_gender="male",
            patient_display_name="Мария",
            patient_age=25,
            therapist_traits=["strict", "business"],
            mark_complete=True,
        )

        assert updated is not None
        assert updated.is_prescreening_complete is True
        assert updated.prescreening_completed_at is not None
        assert isinstance(updated.prescreening_completed_at, datetime)

    async def test_is_prescreening_complete_false(self, db_session):
        """Test checking incomplete prescreening."""
        # Create user without prescreening
        user = User(
            telegram_id=12345,
            username="testuser",
        )
        db_session.add(user)
        await db_session.commit()

        repo = UserRepository(db_session)
        is_complete = await repo.is_prescreening_complete(user.id)

        assert is_complete is False

    async def test_is_prescreening_complete_true(self, db_session):
        """Test checking complete prescreening."""
        # Create user with completed prescreening
        user = User(
            telegram_id=12345,
            username="testuser",
            prescreening_completed_at=datetime.utcnow(),
        )
        db_session.add(user)
        await db_session.commit()

        repo = UserRepository(db_session)
        is_complete = await repo.is_prescreening_complete(user.id)

        assert is_complete is True

    async def test_get_profile(self, db_session):
        """Test getting user profile."""
        # Create user with prescreening
        user = User(
            telegram_id=12345,
            username="testuser",
            therapist_name="Анна",
            therapist_gender="female",
            patient_display_name="Петр",
            patient_age=35,
            therapist_traits=["kind", "calm"],
            prescreening_completed_at=datetime.utcnow(),
        )
        db_session.add(user)
        await db_session.commit()

        repo = UserRepository(db_session)
        profile = await repo.get_profile(user.id)

        assert profile is not None
        assert profile["prescreening_complete"] is True
        assert profile["therapist_profile"]["name"] == "Анна"
        assert profile["therapist_profile"]["gender"] == "female"
        assert profile["therapist_profile"]["traits"] == ["kind", "calm"]
        assert profile["patient_record"]["patient_pseudonym"] == "Петр"
        assert profile["patient_record"]["patient_age"] == "35"

    async def test_get_profile_incomplete(self, db_session):
        """Test getting incomplete profile."""
        # Create user without prescreening
        user = User(
            telegram_id=12345,
            username="testuser",
            patient_pseudonym="СтарыйПсевдоним",
            patient_age_legacy="40",
        )
        db_session.add(user)
        await db_session.commit()

        repo = UserRepository(db_session)
        profile = await repo.get_profile(user.id)

        assert profile is not None
        assert profile["prescreening_complete"] is False
        assert profile["therapist_profile"]["name"] == "Опора"  # Default
        assert profile["therapist_profile"]["gender"] == "female"  # Default
        assert profile["patient_record"]["patient_pseudonym"] == "СтарыйПсевдоним"
        assert profile["patient_record"]["patient_age"] == "40"

    async def test_update_prescreening_profile_not_found(self, db_session):
        """Test updating non-existent user."""
        repo = UserRepository(db_session)
        updated = await repo.update_prescreening_profile(
            user_id=99999,
            therapist_name="Тест",
        )

        assert updated is None

    async def test_is_prescreening_complete_not_found(self, db_session):
        """Test checking prescreening for non-existent user."""
        repo = UserRepository(db_session)
        is_complete = await repo.is_prescreening_complete(99999)

        assert is_complete is False

    async def test_get_profile_not_found(self, db_session):
        """Test getting profile for non-existent user."""
        repo = UserRepository(db_session)
        profile = await repo.get_profile(99999)

        assert profile is None

    async def test_update_patient_card(self, db_session):
        """Test updating intake card fields."""
        user = User(
            telegram_id=43210,
            username="carduser",
        )
        db_session.add(user)
        await db_session.commit()

        repo = UserRepository(db_session)
        updated = await repo.update_patient_card(
            user_id=user.id,
            mental_health="Эпизоды тревожности.",
            physical_health="Проблемы со сном.",
            problems="Сложно концентрироваться.",
            intake_hypothesis="Предварительная тревожная симптоматика.",
            intake_hypothesis_explanation="Связь со стрессом на работе.",
        )

        assert updated is not None
        assert updated.mental_health_history == "Эпизоды тревожности."
        assert updated.physical_health_history == "Проблемы со сном."
        assert updated.current_problems == "Сложно концентрироваться."
        assert updated.intake_hypothesis == "Предварительная тревожная симптоматика."
        assert updated.intake_hypothesis_explanation == "Связь со стрессом на работе."
