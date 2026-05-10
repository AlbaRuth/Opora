"""Unit tests for intake stage orchestration in DialogueService."""

from datetime import datetime
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

# Add project root to path
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.config import get_settings
from db.models import TherapySession, User


@pytest.mark.asyncio
class TestDialogueServiceIntake:
    async def test_start_session_starts_intake_phase_when_enabled(self, db_session, monkeypatch):
        from services.dialogue_service import DialogueService
        monkeypatch.setenv("INTAKE_ENABLED", "true")
        get_settings.cache_clear()

        user = User(
            telegram_id=90001,
            username="intake_user",
            patient_display_name="Ирина",
            patient_age=31,
            prescreening_completed_at=datetime.utcnow(),
        )
        db_session.add(user)
        await db_session.commit()

        service = DialogueService()
        service.therapist_agent = MagicMock()
        service.therapist_agent.start_new_session = AsyncMock()

        result = await service.start_session(telegram_id=90001)

        assert "соберем информацию" in result
        service.therapist_agent.start_new_session.assert_not_called()

        session_obj = (
            await db_session.execute(
                select(TherapySession).where(TherapySession.user_id == user.id)
            )
        ).scalar_one_or_none()
        assert session_obj is not None
        assert session_obj.flow_phase == "intake"

        monkeypatch.setenv("INTAKE_ENABLED", "false")
        get_settings.cache_clear()

    async def test_process_message_routes_to_intake_agent_and_switches_phase(
        self,
        db_session,
        monkeypatch,
    ):
        from services.dialogue_service import DialogueService
        monkeypatch.setenv("INTAKE_ENABLED", "true")
        get_settings.cache_clear()

        user = User(
            telegram_id=90002,
            username="intake_progress",
            patient_display_name="Олег",
            patient_age=29,
            prescreening_completed_at=datetime.utcnow(),
        )
        db_session.add(user)
        await db_session.flush()

        session = TherapySession(
            user_id=user.id,
            session_number=1,
            is_active=True,
            flow_phase="intake",
            intake_user_turns=5,
            dialog_count=5,
        )
        db_session.add(session)
        await db_session.commit()

        service = DialogueService()
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
        assert "достаточно информации" in result["response"]
        service.intake_agent.process_patient_input.assert_awaited_once()
        service.therapist_agent.process_patient_input.assert_not_called()

        await db_session.refresh(session)
        assert session.flow_phase == "therapy"
        assert session.intake_user_turns == 6
        assert session.intake_completed_at is not None

        monkeypatch.setenv("INTAKE_ENABLED", "false")
        get_settings.cache_clear()

    async def test_get_patient_summary_returns_plain_text(self, db_session):
        from services.dialogue_service import DialogueService
        user = User(
            telegram_id=90003,
            username="summary_user",
            patient_display_name="Марина",
            patient_age=34,
            prescreening_completed_at=datetime.utcnow(),
            mental_health_history="Тревожность несколько лет.",
            physical_health_history="Периодические головные боли.",
            current_problems="Нарушение сна, раздражительность.",
            intake_hypothesis="Предварительно: генерализованная тревожность.",
            intake_hypothesis_explanation="Симптомы усиливаются при рабочем стрессе.",
        )
        db_session.add(user)
        await db_session.commit()

        service = DialogueService()
        summary = await service.get_patient_summary(telegram_id=90003)

        assert "Сводка карточки пациента" in summary
        assert "Марина" in summary
        assert "генерализованная тревожность" in summary.lower()
