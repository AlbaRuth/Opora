"""Unit tests for DialogueService async contract."""

import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock

# Add project root to path
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import SessionState directly from file to avoid circular import
sys.path.insert(0, str(_project_root / "agents" / "core"))
from session_state import SessionState
sys.path.pop(0)


class TestDialogueServiceAsyncContract:
    """
    Test that DialogueService correctly awaits async agent methods.
    
    These tests verify the fix for the missing 'await' issue where
    start_new_session and process_patient_input were called without await.
    """

    @pytest.fixture
    def mock_agent(self):
        """Create a properly mocked TherapistAgent."""
        agent = Mock()
        agent.start_new_session = AsyncMock(return_value={
            "patient_id": "123",
            "session_id": "123_1",
            "therapist_response": "Hello! I'm here to help.",
            "current_therapy": "cognitive-behavioral therapy",
            "reason": "Initial session",
        })
        agent.process_patient_input = AsyncMock(return_value={
            "therapist_response": "I understand how you feel.",
            "session_ended": False,
            "current_therapy": "cognitive-behavioral therapy",
            "strategy": {"strategy": "validation", "strategy_text": "Validate feelings"},
        })
        return agent

    @pytest.fixture
    def service(self, mock_agent):
        """Create DialogueService with mocked agent - import here to avoid circular import."""
        from services.dialogue_service import DialogueService
        return DialogueService(therapist_agent=mock_agent)

    async def test_start_session_awaits_agent_method(self, service, mock_agent):
        """
        Verify that start_session properly awaits start_new_session.

        Before the fix, this would have been a coroutine that was never awaited,
        causing the method to return a coroutine object instead of the actual result.
        """
        from datetime import datetime

        # Mock database operations
        with patch("services.dialogue_service.get_db_session") as mock_get_db:
            mock_context = AsyncMock()
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock repositories with prescreening complete user
            mock_user = MagicMock()
            mock_user.id = 123
            mock_user.patient_pseudonym = "TestUser"
            mock_user.patient_display_name = "TestUser"
            mock_user.patient_age = 30
            mock_user.therapist_name = "Опора"
            mock_user.therapist_gender = "female"
            mock_user.therapist_traits = []
            mock_user.prescreening_completed_at = datetime.utcnow()
            mock_user.is_prescreening_complete = True

            mock_user_repo = MagicMock()
            mock_user_repo.get_by_telegram_id = AsyncMock(return_value=mock_user)
            mock_user_repo.is_prescreening_complete = AsyncMock(return_value=True)

            mock_session_repo = MagicMock()
            mock_session_repo.get_active_session = AsyncMock(return_value=None)
            mock_session_repo.get_latest_session = AsyncMock(return_value=None)
            mock_session_repo.create_session = AsyncMock(return_value=MagicMock(id=456))
            mock_session_repo.update_therapy = AsyncMock()

            with patch("services.dialogue_service.UserRepository", return_value=mock_user_repo):
                with patch("services.dialogue_service.SessionRepository", return_value=mock_session_repo):
                    result = await service.start_session(
                        telegram_id=123456,
                        username="testuser",
                    )

        # Verify the agent method was awaited (called as async)
        mock_agent.start_new_session.assert_awaited_once()

        # Verify we got the actual response, not a coroutine
        assert result == "Hello! I'm here to help."
        assert isinstance(result, str)

    async def test_process_message_awaits_agent_method(self, service, mock_agent):
        """
        Verify that process_message properly awaits process_patient_input.

        Before the fix, this would have returned a coroutine object instead
        of the actual processing result, causing downstream errors.
        """
        from datetime import datetime

        with patch("services.dialogue_service.get_db_session") as mock_get_db:
            mock_context = AsyncMock()
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock user with completed prescreening
            mock_user = MagicMock()
            mock_user.id = 123
            mock_user.is_prescreening_complete = True
            mock_user.prescreening_completed_at = datetime.utcnow()
            mock_user.patient_display_name = "TestUser"
            mock_user.patient_age = 30
            mock_user.therapist_name = "Опора"
            mock_user.therapist_gender = "female"
            mock_user.therapist_traits = []

            mock_user_repo = MagicMock()
            mock_user_repo.get_by_telegram_id = AsyncMock(return_value=mock_user)

            mock_session_repo = MagicMock()
            mock_session_repo.get_active_session = AsyncMock(return_value=MagicMock(
                id=456,
                user_id=123,
                session_number=1,
                dialog_count=2,
                therapy_type="cbt",
                current_stage="assessment",
            ))
            mock_session_repo.acquire_session_lock = AsyncMock()
            mock_session_repo.increment_dialog_count = AsyncMock()
            mock_session_repo.update_therapy = AsyncMock()
            mock_session_repo.update_current_stage = AsyncMock()

            mock_message_repo = MagicMock()
            mock_message_repo.get_message_count = AsyncMock(return_value=4)
            mock_message_repo.create_message = AsyncMock()

            with patch("services.dialogue_service.UserRepository", return_value=mock_user_repo):
                with patch("services.dialogue_service.SessionRepository", return_value=mock_session_repo):
                    with patch("services.dialogue_service.MessageRepository", return_value=mock_message_repo):
                        result = await service.process_message(
                            telegram_id=123456,
                            text="I feel anxious",
                        )

        # Verify the agent method was awaited
        mock_agent.process_patient_input.assert_awaited_once()

        # Verify call was made with correct arguments
        call_args = mock_agent.process_patient_input.call_args
        assert "state" in call_args.kwargs or any(isinstance(arg, SessionState) for arg in call_args.args)

        # Verify we got the actual dict result, not a coroutine
        assert isinstance(result, dict)
        assert "response" in result
        assert result["response"] == "I understand how you feel."

    async def test_session_state_passed_to_agent(self, service, mock_agent):
        """
        Verify that SessionState DTO is properly constructed and passed to agent.
        """
        from datetime import datetime

        with patch("services.dialogue_service.get_db_session") as mock_get_db:
            mock_context = AsyncMock()
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock user with completed prescreening and profile
            mock_user = MagicMock()
            mock_user.id = 123
            mock_user.is_prescreening_complete = True
            mock_user.prescreening_completed_at = datetime.utcnow()
            mock_user.patient_display_name = "TestPatient"
            mock_user.patient_age = 28
            mock_user.therapist_name = "Доктор Анна"
            mock_user.therapist_gender = "female"
            mock_user.therapist_traits = ["calm", "empathetic"]

            mock_user_repo = MagicMock()
            mock_user_repo.get_by_telegram_id = AsyncMock(return_value=mock_user)

            mock_session_repo = MagicMock()
            mock_session_repo.get_active_session = AsyncMock(return_value=MagicMock(
                id=789,
                user_id=123,
                session_number=3,
                dialog_count=5,
                therapy_type="psychodynamic",
                current_stage="working_through",
            ))
            mock_session_repo.acquire_session_lock = AsyncMock()
            mock_session_repo.increment_dialog_count = AsyncMock()
            mock_session_repo.update_therapy = AsyncMock()
            mock_session_repo.update_current_stage = AsyncMock()

            mock_message_repo = MagicMock()
            mock_message_repo.get_message_count = AsyncMock(return_value=10)
            mock_message_repo.create_message = AsyncMock()

            with patch("services.dialogue_service.UserRepository", return_value=mock_user_repo):
                with patch("services.dialogue_service.SessionRepository", return_value=mock_session_repo):
                    with patch("services.dialogue_service.MessageRepository", return_value=mock_message_repo):
                        await service.process_message(
                            telegram_id=123456,
                            text="Test message",
                        )

        # Verify SessionState was properly constructed with DB values and profile
        call_args = mock_agent.process_patient_input.call_args
        state_arg = None

        # Find SessionState in call arguments
        for arg in call_args.args:
            if isinstance(arg, SessionState):
                state_arg = arg
                break
        if call_args.kwargs.get("state"):
            state_arg = call_args.kwargs["state"]

        assert state_arg is not None, "SessionState should be passed to agent"
        assert state_arg.patient_id == "123"
        assert state_arg.session_db_id == 789
        assert state_arg.session_counter == 3
        assert state_arg.dialog_count == 5
        assert state_arg.current_therapy == "psychodynamic"
        assert state_arg.current_stage == "working_through"
        # Verify profile fields are passed
        assert state_arg.therapist_name == "Доктор Анна"
        assert state_arg.therapist_gender == "female"
        assert state_arg.therapist_traits == ["calm", "empathetic"]
        assert state_arg.patient_display_name == "TestPatient"
        assert state_arg.patient_age == 28
