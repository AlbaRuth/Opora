"""Unit tests for DialogueService prescreening / anket (v2 schema)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.factories import create_account_with_prescreening, fill_clinical_card_minimal


@pytest.mark.asyncio
class TestDialogueServicePrescreening:
    async def test_start_session_returns_none_for_new_user(
        self, db_session, patch_get_db_session
    ):
        from services.dialogue_service import DialogueService

        patch_get_db_session("services.dialogue_service")
        service = DialogueService()
        service.therapist_agent = MagicMock()
        service.therapist_agent.start_new_session = AsyncMock()

        result = await service.start_session(
            telegram_id=912345,
            username="newuser",
            first_name="New",
        )
        assert result is None
        service.therapist_agent.start_new_session.assert_not_called()

    async def test_start_session_returns_greeting_for_complete_user(
        self, db_session, patch_get_db_session
    ):
        from services.dialogue_service import DialogueService

        patch_get_db_session("services.dialogue_service")
        await create_account_with_prescreening(
            db_session,
            912346,
            therapist_name="Анна",
            patient_display_name="Иван",
            patient_age=30,
        )

        service = DialogueService()
        service.therapist_agent = MagicMock()
        service.therapist_agent.start_new_session = AsyncMock(
            return_value={
                "therapist_response": "Hello! I'm Anna.",
                "current_therapy": "CBT",
                "reason": "Test therapy",
            }
        )

        result = await service.start_session(telegram_id=912346)
        assert result == "Hello! I'm Anna."
        call_args = service.therapist_agent.start_new_session.call_args
        state = call_args.kwargs["state"]
        assert state.therapist_name == "Анна"
        assert state.patient_display_name == "Иван"
        assert state.patient_age == 30

    async def test_start_session_returns_none_for_incomplete_user(
        self, db_session, patch_get_db_session
    ):
        from services.dialogue_service import DialogueService

        patch_get_db_session("services.dialogue_service")
        await create_account_with_prescreening(
            db_session,
            912347,
            mark_prescreening_complete=False,
        )

        service = DialogueService()
        service.therapist_agent = MagicMock()
        service.therapist_agent.start_new_session = AsyncMock()

        result = await service.start_session(telegram_id=912347)
        assert result is None
        service.therapist_agent.start_new_session.assert_not_called()

    async def test_process_message_requires_prescreening(
        self, db_session, patch_get_db_session
    ):
        from services.dialogue_service import DialogueService

        patch_get_db_session("services.dialogue_service")
        await create_account_with_prescreening(
            db_session,
            912348,
            mark_prescreening_complete=False,
        )

        service = DialogueService()
        result = await service.process_message(telegram_id=912348, text="Hello")
        assert "профил" in result["response"] or "завершите" in result["response"]
        assert result["session_ended"] is False

    async def test_process_message_includes_profile_in_state(
        self,
        db_session,
        patch_get_db_session,
        dialogue_langfuse_stub,
    ):
        from services.dialogue_service import DialogueService
        from tests.factories import create_active_therapy_session

        patch_get_db_session("services.dialogue_service")
        account = await create_account_with_prescreening(
            db_session,
            912349,
            therapist_name="Доктор Иван",
            therapist_gender="male",
            patient_display_name="Мария",
            patient_age=25,
            therapist_styles=["friendly", "soft"],
        )
        await create_active_therapy_session(db_session, account.id, flow_phase="therapy")

        service = DialogueService()
        service.therapist_agent = MagicMock()
        service.therapist_agent.process_patient_input = AsyncMock(
            return_value={
                "therapist_response": "I understand, Maria.",
                "session_ended": False,
                "current_therapy": "general",
                "strategy": {"strategy": "validation"},
            }
        )

        result = await service.process_message(
            telegram_id=912349,
            text="I'm feeling sad",
        )
        assert "Maria" in result["response"] or "understand" in result["response"]
        call_args = service.therapist_agent.process_patient_input.call_args
        state = call_args.kwargs["state"]
        assert state.therapist_name == "Доктор Иван"
        assert state.therapist_gender == "male"
        assert state.patient_display_name == "Мария"
        assert state.patient_age == 25

    async def test_start_session_uses_default_profile_values(
        self, db_session, patch_get_db_session
    ):
        from services.dialogue_service import DialogueService

        patch_get_db_session("services.dialogue_service")
        await create_account_with_prescreening(
            db_session,
            912350,
            therapist_name="Опора",
            therapist_gender="female",
            therapist_styles=[],
            patient_display_name="",
            patient_age=None,
        )

        service = DialogueService()
        service.therapist_agent = MagicMock()
        service.therapist_agent.start_new_session = AsyncMock(
            return_value={"therapist_response": "Hello!", "current_therapy": "general"}
        )

        await service.start_session(telegram_id=912350)
        state = service.therapist_agent.start_new_session.call_args.kwargs["state"]
        assert state.therapist_name == "Опора"
        assert state.therapist_gender == "female"
        assert state.therapist_styles == []
        assert state.patient_display_name == ""
        assert state.patient_age is None

    async def test_start_session_intake_branch_card_incomplete(
        self, db_session, patch_get_db_session, monkeypatch
    ):
        from services.dialogue_service import DialogueService

        patch_get_db_session("services.dialogue_service")
        await create_account_with_prescreening(
            db_session,
            912351,
            therapist_name="Анна",
            patient_display_name="Иван",
        )

        service = DialogueService()
        monkeypatch.setattr(service.settings, "intake_enabled", True)
        monkeypatch.setattr(service.settings, "intake_min_user_turns", 4)
        monkeypatch.setattr(service.settings, "intake_max_user_turns_multiplier", 3)
        service.therapist_agent = MagicMock()

        result = await service.start_session(telegram_id=912351)
        assert result is not None
        assert "информацию" in result.lower() or "собрать" in result.lower()
        assert "от 4 до 12" in result
        assert "клинической карточки" in result

    async def test_start_session_intake_branch_card_complete(
        self, db_session, patch_get_db_session, monkeypatch
    ):
        from services.dialogue_service import DialogueService

        patch_get_db_session("services.dialogue_service")
        account = await create_account_with_prescreening(
            db_session,
            912352,
            therapist_name="Анна",
            patient_display_name="Иван",
        )
        await fill_clinical_card_minimal(
            db_session,
            account.id,
            current_problems="Feeling anxious at work",
            mental_health_history="History of anxiety",
        )

        service = DialogueService()
        monkeypatch.setattr(service.settings, "intake_enabled", True)

        result = await service.start_session(telegram_id=912352)
        assert result is not None
        assert "Иван" in result or "друг" in result
        assert "день" in result.lower()

        from sqlalchemy import select
        from db.models import TherapySession
        from db.repositories import IntakeStateRepository

        res = await db_session.execute(
            select(TherapySession)
            .where(TherapySession.account_id == account.id)
            .order_by(TherapySession.id.desc())
            .limit(1)
        )
        ts = res.scalar_one()
        st = await IntakeStateRepository(db_session).get_by_session_id(ts.id)
        assert st is not None and st.flow_phase == "therapy"

    async def test_get_user_anket_returns_profile(self, db_session, patch_get_db_session):
        from services.dialogue_service import DialogueService

        patch_get_db_session("services.dialogue_service")
        await create_account_with_prescreening(
            db_session,
            912353,
            therapist_name="Доктор Смит",
            therapist_gender="male",
            patient_display_name="Мария",
            patient_age=25,
            therapist_styles=["friendly", "soft"],
            patient_sex="female",
            address_mode="formal",
        )

        service = DialogueService()
        result = await service.get_user_anket(telegram_id=912353)
        assert "Доктор Смит" in result
        assert "Мария" in result
        assert "25" in result

    async def test_get_user_anket_requires_prescreening(
        self, db_session, patch_get_db_session
    ):
        from services.dialogue_service import DialogueService

        patch_get_db_session("services.dialogue_service")
        await create_account_with_prescreening(
            db_session,
            912354,
            mark_prescreening_complete=False,
        )

        service = DialogueService()
        result = await service.get_user_anket(telegram_id=912354)
        assert "профил" in result.lower() or "завершите" in result.lower() or "старт" in result.lower()

    async def test_get_user_anket_user_not_found(self, db_session, patch_get_db_session):
        from services.dialogue_service import DialogueService

        patch_get_db_session("services.dialogue_service")
        service = DialogueService()
        result = await service.get_user_anket(telegram_id=999999991)
        assert "не найден" in result.lower() or "start" in result.lower()
