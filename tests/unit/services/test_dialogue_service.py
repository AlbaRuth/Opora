"""Unit tests for DialogueService async contract (v2 schema)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.core.session_state import SessionState
from tests.factories import (
    create_account_with_prescreening,
    create_active_therapy_session,
)


class TestDialogueServiceAsyncContract:
    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock()
        agent.start_new_session = AsyncMock(
            return_value={
                "patient_id": "123",
                "session_id": "123_1",
                "therapist_response": "Hello! I'm here to help.",
                "current_therapy": "cognitive-behavioral therapy",
                "reason": "Initial session",
            }
        )
        agent.process_patient_input = AsyncMock(
            return_value={
                "therapist_response": "I understand how you feel.",
                "session_ended": False,
                "current_therapy": "cognitive-behavioral therapy",
                "strategy": {"strategy": "validation", "strategy_text": "Validate feelings"},
            }
        )
        return agent

    @pytest.fixture
    def service(self, mock_agent):
        from services.dialogue_service import DialogueService

        return DialogueService(therapist_agent=mock_agent)

    @pytest.mark.asyncio
    async def test_start_session_awaits_agent_method(
        self, service, mock_agent, db_session, patch_get_db_session
    ):
        patch_get_db_session("services.dialogue_service")
        await create_account_with_prescreening(
            db_session,
            123456,
            therapist_name="Анна",
            patient_display_name="TestUser",
            patient_age=30,
        )

        result = await service.start_session(
            telegram_id=123456,
            username="testuser",
        )

        mock_agent.start_new_session.assert_awaited_once()
        assert result == "Hello! I'm here to help."
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_process_message_awaits_agent_method(
        self,
        service,
        mock_agent,
        db_session,
        patch_get_db_session,
        dialogue_langfuse_stub,
    ):
        patch_get_db_session("services.dialogue_service")
        account = await create_account_with_prescreening(
            db_session,
            223456,
            therapist_name="Опора",
            patient_display_name="TestUser",
            patient_age=30,
        )
        ts, _ = await create_active_therapy_session(db_session, account.id, flow_phase="therapy")
        ts.dialog_count = 2
        ts.therapy_type = "cbt"
        ts.current_stage = "assessment"
        await db_session.flush()

        result = await service.process_message(
            telegram_id=223456,
            text="I feel anxious",
        )

        mock_agent.process_patient_input.assert_awaited_once()
        call_args = mock_agent.process_patient_input.call_args
        assert "state" in call_args.kwargs or any(
            isinstance(a, SessionState) for a in call_args.args
        )
        assert isinstance(result, dict)
        assert "response" in result
        assert result["response"] == "I understand how you feel."

    @pytest.mark.asyncio
    async def test_session_state_passed_to_agent(
        self,
        service,
        mock_agent,
        db_session,
        patch_get_db_session,
        dialogue_langfuse_stub,
    ):
        patch_get_db_session("services.dialogue_service")
        account = await create_account_with_prescreening(
            db_session,
            323456,
            therapist_name="Доктор Анна",
            therapist_gender="female",
            patient_display_name="TestPatient",
            patient_age=28,
            therapist_styles=["friendly", "soft"],
        )
        ts, _ = await create_active_therapy_session(db_session, account.id, flow_phase="therapy")
        ts.dialog_count = 5
        ts.therapy_type = "psychodynamic"
        ts.current_stage = "working_through"
        await db_session.flush()

        await service.process_message(
            telegram_id=323456,
            text="Test message",
        )

        call_args = mock_agent.process_patient_input.call_args
        state_arg = call_args.kwargs.get("state")
        if state_arg is None:
            for arg in call_args.args:
                if isinstance(arg, SessionState):
                    state_arg = arg
                    break

        assert state_arg is not None
        assert state_arg.patient_id == str(account.id)
        assert state_arg.session_db_id == ts.id
        assert state_arg.session_counter == ts.session_number
        assert state_arg.dialog_count == ts.dialog_count
        assert state_arg.current_therapy == "psychodynamic"
        assert state_arg.current_stage == "working_through"
        assert state_arg.therapist_name == "Доктор Анна"
        assert state_arg.therapist_gender == "female"
        assert state_arg.therapist_styles == ["friendly", "soft"]
        assert state_arg.patient_display_name == "TestPatient"
        assert state_arg.patient_age == 28


class TestDialogueServiceResetUserData:
    """Test reset_user_data method for complete user deletion."""

    @pytest.fixture
    def service(self):
        from services.dialogue_service import DialogueService

        return DialogueService()

    @pytest.mark.asyncio
    async def test_reset_user_data_deletes_existing_user(
        self, service, db_session, patch_get_db_session
    ):
        """Test that reset_user_data deletes existing user and returns True."""
        patch_get_db_session("services.dialogue_service")
        account = await create_account_with_prescreening(
            db_session,
            423456,
            therapist_name="Тест",
            patient_display_name="TestUser",
            patient_age=30,
        )
        # Create a session to verify cascade deletion
        await create_active_therapy_session(db_session, account.id, flow_phase="therapy")

        # Verify account exists
        from db.repositories import AccountRepository
        repo = AccountRepository(db_session)
        existing = await repo.get_by_telegram_id(423456)
        assert existing is not None

        # Reset user data
        result = await service.reset_user_data(telegram_id=423456)
        assert result is True

        # Verify account is deleted (need fresh session to avoid cache)
        await db_session.commit()
        deleted = await repo.get_by_telegram_id(423456)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_reset_user_data_returns_false_for_nonexistent_user(
        self, service, db_session, patch_get_db_session
    ):
        """Test that reset_user_data returns False when user doesn't exist."""
        patch_get_db_session("services.dialogue_service")

        # Try to delete non-existent user
        result = await service.reset_user_data(telegram_id=999999)
        assert result is False
