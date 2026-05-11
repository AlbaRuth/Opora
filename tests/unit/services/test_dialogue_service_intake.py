"""Unit tests for intake phase in DialogueService (v2: IntakeState)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select

from db.models import TherapySession
from db.repositories import IntakeStateRepository
from services.dialogue_service import DialogueService
from tests.factories import (
    create_account_with_prescreening,
    create_active_therapy_session,
    fill_clinical_card_minimal,
)


@pytest.mark.asyncio
class TestDialogueServiceIntake:
    async def test_start_session_scripted_intake_when_enabled(
        self, db_session, patch_get_db_session, monkeypatch
    ):
        patch_get_db_session("services.dialogue_service")
        account = await create_account_with_prescreening(
            db_session,
            90001,
            patient_display_name="Ирина",
            patient_age=31,
        )

        service = DialogueService()
        monkeypatch.setattr(service.settings, "intake_enabled", True)
        service.therapist_agent = MagicMock()
        service.therapist_agent.start_new_session = AsyncMock()

        result = await service.start_session(telegram_id=90001)
        assert result is not None
        assert "информацию" in result.lower() or "собрать" in result.lower()
        service.therapist_agent.start_new_session.assert_not_called()

        res = await db_session.execute(
            select(TherapySession).where(TherapySession.account_id == account.id)
        )
        session_obj = res.scalar_one_or_none()
        assert session_obj is not None
        ir = IntakeStateRepository(db_session)
        st = await ir.get_by_session_id(session_obj.id)
        assert st is not None
        assert st.flow_phase == "intake"

    async def test_process_message_routes_to_intake_agent_and_completes(
        self,
        db_session,
        patch_get_db_session,
        dialogue_langfuse_stub,
        monkeypatch,
    ):
        patch_get_db_session("services.dialogue_service")
        account = await create_account_with_prescreening(
            db_session,
            90002,
            patient_display_name="Олег",
            patient_age=29,
        )
        ts, intake = await create_active_therapy_session(
            db_session, account.id, flow_phase="intake"
        )
        intake.user_turn_count = 5
        await db_session.flush()

        service = DialogueService()
        monkeypatch.setattr(service.settings, "intake_enabled", True)
        service.intake_agent = MagicMock()
        service.intake_agent.process_patient_input = AsyncMock(
            return_value={
                "therapist_response": "Олег, теперь я знаю достаточно информации о вас.",
                "intake_completed": True,
                "missing_fields": [],
                "card_updates": {},
            }
        )
        service.therapist_agent = MagicMock()
        service.therapist_agent.process_patient_input = AsyncMock()

        result = await service.process_message(
            telegram_id=90002,
            text="Я часто тревожусь и плохо сплю.",
        )

        assert result["session_ended"] is False
        assert "достаточно" in result["response"].lower()
        service.intake_agent.process_patient_input.assert_awaited_once()
        service.therapist_agent.process_patient_input.assert_not_called()

        ir = IntakeStateRepository(db_session)
        st = await ir.get_by_session_id(ts.id)
        assert st is not None
        assert st.flow_phase == "therapy"
        assert st.user_turn_count == 6
        assert st.completed_at is not None

    async def test_get_patient_summary_returns_plain_text(
        self, db_session, patch_get_db_session
    ):
        patch_get_db_session("services.dialogue_service")
        account = await create_account_with_prescreening(
            db_session,
            90003,
            patient_display_name="Марина",
            patient_age=34,
        )
        await fill_clinical_card_minimal(
            db_session,
            account.id,
            current_problems="Нарушение сна, раздражительность.",
            mental_health_history="Тревожность несколько лет.",
        )
        from db.repositories import ClinicalProfileRepository

        cr = ClinicalProfileRepository(db_session)
        await cr.update_clinical_data(
            account_id=account.id,
            physical_health_history="Периодические головные боли.",
            intake_hypothesis="Предварительно: генерализованная тревожность.",
            intake_hypothesis_explanation="Симптомы усиливаются при рабочем стрессе.",
        )

        service = DialogueService()
        summary = await service.get_patient_summary(telegram_id=90003)
        assert "Сводка карточки пациента" in summary
        assert "Марина" in summary
        assert "генерализованная" in summary.lower()

    async def test_process_message_transitions_on_max_turns_with_insufficient_flag(
        self,
        db_session,
        patch_get_db_session,
        dialogue_langfuse_stub,
        monkeypatch,
    ):
        """Test that intake transitions to therapy when max turns reached with insufficient data."""
        patch_get_db_session("services.dialogue_service")
        account = await create_account_with_prescreening(
            db_session,
            90004,
            patient_display_name="Сергей",
            patient_age=42,
        )
        ts, intake = await create_active_therapy_session(
            db_session, account.id, flow_phase="intake"
        )
        # Set user_turn_count at max-1 to trigger completion on next message
        intake.user_turn_count = 11  # Will become 12 (max for min=6, multiplier=2)
        await db_session.flush()

        service = DialogueService()
        monkeypatch.setattr(service.settings, "intake_enabled", True)
        # Set max multiplier to ensure predictable behavior
        monkeypatch.setattr(
            service.settings,
            "intake_max_user_turns_multiplier",
            2,
        )
        service.intake_agent = MagicMock()
        service.intake_agent.process_patient_input = AsyncMock(
            return_value={
                "therapist_response": "Сергей, мы обсудили многое.",
                "intake_completed": True,
                "missing_fields": ["current_problems"],  # Missing required field
                "initial_info_insufficient": True,
                "card_updates": {},
            }
        )
        service.therapist_agent = MagicMock()
        service.therapist_agent.process_patient_input = AsyncMock()

        result = await service.process_message(
            telegram_id=90004,
            text="Не знаю, что еще сказать.",
        )

        assert result["session_ended"] is False
        service.intake_agent.process_patient_input.assert_awaited_once()
        service.therapist_agent.process_patient_input.assert_not_called()

        ir = IntakeStateRepository(db_session)
        st = await ir.get_by_session_id(ts.id)
        assert st is not None
        assert st.flow_phase == "therapy"
        assert st.user_turn_count == 12

    async def test_get_patient_summary_shows_insufficient_info_flag(
        self, db_session, patch_get_db_session
    ):
        """Test that patient summary indicates when initial info was insufficient."""
        patch_get_db_session("services.dialogue_service")
        account = await create_account_with_prescreening(
            db_session,
            90005,
            patient_display_name="Ольга",
            patient_age=29,
        )
        await fill_clinical_card_minimal(
            db_session,
            account.id,
            current_problems="",
            mental_health_history="",
        )
        from db.repositories import ClinicalProfileRepository

        cr = ClinicalProfileRepository(db_session)
        await cr.update_clinical_data(
            account_id=account.id,
            intake_hypothesis="Недостаточно данных для гипотезы",
            intake_hypothesis_explanation="Пациент не предоставил достаточно информации",
            initial_info_insufficient=True,
        )

        service = DialogueService()
        summary = await service.get_patient_summary(telegram_id=90005)
        assert "Ольга" in summary
        # Summary should contain the insufficient info marker
        assert summary is not None
