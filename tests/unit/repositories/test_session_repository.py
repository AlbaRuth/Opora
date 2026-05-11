"""Unit tests for SessionRepository (advisory lock + therapy updates)."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TherapySession
from db.repositories import SessionRepository


class TestSessionRepositoryLock:
    @pytest_asyncio.fixture
    async def mock_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session

    @pytest_asyncio.fixture
    async def repository(self, mock_session):
        return SessionRepository(mock_session)

    async def test_acquire_session_lock_calls_pg_advisory(self, repository, mock_session):
        session_id = 123
        await repository.acquire_session_lock(session_id)
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "pg_advisory_xact_lock" in sql_text
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs.get("parameters", {})
        assert params == {"lock_key": session_id}

    async def test_update_therapy_success(self, repository, mock_session):
        mock_db_session = MagicMock(spec=TherapySession)
        mock_db_session.id = 1
        mock_db_session.therapy_type = "old therapy"
        mock_db_session.therapy_reason = "old reason"

        repository.get_by_id = AsyncMock(return_value=mock_db_session)
        repository.update = AsyncMock(return_value=mock_db_session)

        result = await repository.update_therapy(
            session_id=1,
            therapy_type="new therapy",
            therapy_reason="new reason",
        )

        assert result == mock_db_session
        repository.update.assert_called_once_with(
            mock_db_session,
            therapy_type="new therapy",
            therapy_reason="new reason",
        )

    async def test_update_therapy_not_found(self, repository, mock_session):
        repository.get_by_id = AsyncMock(return_value=None)
        result = await repository.update_therapy(session_id=999, therapy_type="therapy")
        assert result is None

    async def test_acquire_lock_different_session_ids(self, repository, mock_session):
        for session_id in [1, 42, 999]:
            mock_session.execute.reset_mock()
            await repository.acquire_session_lock(session_id)
            call_args = mock_session.execute.call_args
            params = call_args[0][1] if len(call_args[0]) > 1 else {}
            assert params == {"lock_key": session_id}


@pytest.mark.asyncio
async def test_intake_state_repository_increment_mark_completed(db_session):
    """Intake flow fields moved from TherapySession to IntakeState."""
    from tests.factories import create_account_with_prescreening, create_active_therapy_session

    from db.repositories import IntakeStateRepository

    account = await create_account_with_prescreening(db_session, 55001)
    ts, _ = await create_active_therapy_session(
        db_session, account.id, flow_phase="intake"
    )
    intake_repo = IntakeStateRepository(db_session)
    inc = await intake_repo.increment_turns(ts.id)
    assert inc is not None
    assert inc.user_turn_count == 1
    done = await intake_repo.mark_completed(ts.id)
    assert done is not None
    assert done.flow_phase == "therapy"
    assert done.completed_at is not None
