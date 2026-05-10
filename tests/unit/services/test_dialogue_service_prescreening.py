"""
Unit tests for DialogueService with prescreening checks.
"""

import sys
from pathlib import Path
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from db.models import User, TherapySession


@pytest.mark.asyncio
class TestDialogueServicePrescreening:
    """Test DialogueService prescreening integration."""

    async def test_start_session_returns_none_for_new_user(self, db_session):
        """Test that start_session returns None for new user (needs prescreening)."""
        from services.dialogue_service import DialogueService
        service = DialogueService()

        # Mock the therapist agent
        service.therapist_agent = MagicMock()
        service.therapist_agent.start_new_session = AsyncMock()

        # Call start_session for new user
        result = await service.start_session(
            telegram_id=12345,
            username="newuser",
            first_name="New",
        )

        # Should return None (prescreening required)
        assert result is None

        # Agent should not be called
        service.therapist_agent.start_new_session.assert_not_called()

    async def test_start_session_returns_greeting_for_complete_user(self, db_session):
        """Test that start_session works for user with completed prescreening."""
        from services.dialogue_service import DialogueService
        # Create user with completed prescreening
        user = User(
            telegram_id=12345,
            username="existinguser",
            therapist_name="Анна",
            therapist_gender="female",
            patient_display_name="Иван",
            patient_age=30,
            therapist_traits=["calm"],
            prescreening_completed_at=datetime.utcnow(),
        )
        db_session.add(user)
        await db_session.commit()

        service = DialogueService()

        # Mock the therapist agent
        service.therapist_agent = MagicMock()
        service.therapist_agent.start_new_session = AsyncMock(return_value={
            "therapist_response": "Hello! I'm Anna.",
            "current_therapy": "CBT",
            "reason": "Test therapy",
        })

        # Call start_session
        result = await service.start_session(telegram_id=12345)

        # Should return greeting
        assert result == "Hello! I'm Anna."

        # Verify agent was called with profile
        call_args = service.therapist_agent.start_new_session.call_args
        state = call_args[1]["state"]
        assert state.therapist_name == "Анна"
        assert state.therapist_gender == "female"
        assert state.patient_display_name == "Иван"
        assert state.patient_age == 30
        assert state.therapist_traits == ["calm"]

    async def test_start_session_returns_none_for_incomplete_user(self, db_session):
        """Test that start_session returns None for user with incomplete prescreening."""
        from services.dialogue_service import DialogueService
        # Create user without completed prescreening
        user = User(
            telegram_id=12345,
            username="incompleteuser",
            prescreening_completed_at=None,
        )
        db_session.add(user)
        await db_session.commit()

        service = DialogueService()

        # Mock the therapist agent
        service.therapist_agent = MagicMock()
        service.therapist_agent.start_new_session = AsyncMock()

        # Call start_session
        result = await service.start_session(telegram_id=12345)

        # Should return None (prescreening required)
        assert result is None

        # Agent should not be called
        service.therapist_agent.start_new_session.assert_not_called()

    async def test_process_message_requires_prescreening(self, db_session):
        """Test that process_message returns error for user without prescreening."""
        from services.dialogue_service import DialogueService
        # Create user without prescreening
        user = User(
            telegram_id=12345,
            username="incompleteuser",
            prescreening_completed_at=None,
        )
        db_session.add(user)
        await db_session.commit()

        service = DialogueService()

        # Call process_message
        result = await service.process_message(
            telegram_id=12345,
            text="Hello",
        )

        # Should return error message in Russian
        assert "профиля" in result["response"] or "завершите" in result["response"]
        assert result["session_ended"] is False

    async def test_process_message_includes_profile_in_state(self, db_session):
        """Test that process_message passes profile to agent."""
        from services.dialogue_service import DialogueService
        # Create user with completed prescreening
        user = User(
            telegram_id=12345,
            username="completeuser",
            therapist_name="Доктор Иван",
            therapist_gender="male",
            patient_display_name="Мария",
            patient_age=25,
            therapist_traits=["empathetic", "calm"],
            prescreening_completed_at=datetime.utcnow(),
        )
        db_session.add(user)

        # Create active session
        session = TherapySession(
            user_id=user.id,
            session_number=1,
            is_active=True,
            dialog_count=0,
        )
        db_session.add(session)
        await db_session.commit()

        service = DialogueService()

        # Mock the therapist agent
        service.therapist_agent = MagicMock()
        service.therapist_agent.process_patient_input = AsyncMock(return_value={
            "therapist_response": "I understand, Maria.",
            "session_ended": False,
            "current_therapy": "general",
            "strategy": {"strategy": "validation"},
        })

        # Call process_message
        result = await service.process_message(
            telegram_id=12345,
            text="I'm feeling sad",
        )

        # Verify agent was called with profile
        call_args = service.therapist_agent.process_patient_input.call_args
        state = call_args[1]["state"]
        assert state.therapist_name == "Доктор Иван"
        assert state.therapist_gender == "male"
        assert state.patient_display_name == "Мария"
        assert state.patient_age == 25
        assert state.therapist_traits == ["empathetic", "calm"]

    async def test_start_session_uses_default_profile_values(self, db_session):
        """Test that start_session uses default values when profile fields are empty."""
        from services.dialogue_service import DialogueService
        # Create user with completed prescreening but empty fields
        user = User(
            telegram_id=12345,
            username="defaultuser",
            therapist_name=None,
            therapist_gender=None,
            patient_display_name=None,
            patient_age=None,
            therapist_traits=None,
            prescreening_completed_at=datetime.utcnow(),
        )
        db_session.add(user)
        await db_session.commit()

        service = DialogueService()

        # Mock the therapist agent
        service.therapist_agent = MagicMock()
        service.therapist_agent.start_new_session = AsyncMock(return_value={
            "therapist_response": "Hello!",
            "current_therapy": "general",
        })

        # Call start_session
        await service.start_session(telegram_id=12345)

        # Verify defaults were used
        call_args = service.therapist_agent.start_new_session.call_args
        state = call_args[1]["state"]
        assert state.therapist_name == "Опора"  # Default
        assert state.therapist_gender == "female"  # Default
        assert state.therapist_traits == []
        assert state.patient_display_name == ""
        assert state.patient_age is None
