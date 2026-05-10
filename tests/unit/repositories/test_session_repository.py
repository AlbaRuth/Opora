"""Unit tests for SessionRepository with lock functionality."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import SessionRepository
from db.models import TherapySession


class TestSessionRepositoryLock:
    """Test PostgreSQL advisory lock functionality."""

    @pytest_asyncio.fixture
    async def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session

    @pytest_asyncio.fixture
    async def repository(self, mock_session):
        """Create repository with mock session."""
        return SessionRepository(mock_session)

    async def test_acquire_session_lock_calls_pg_advisory(self, repository, mock_session):
        """Test that acquire_session_lock calls pg_advisory_xact_lock."""
        session_id = 123
        
        await repository.acquire_session_lock(session_id)
        
        # Verify execute was called with lock query
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        
        # Check the SQL text contains advisory lock
        sql_text = str(call_args[0][0])
        assert "pg_advisory_xact_lock" in sql_text
        
        # Check the parameter (passed as second positional argument dict)
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs
        assert params == {"lock_key": session_id}

    async def test_update_therapy_success(self, repository, mock_session):
        """Test updating therapy metadata."""
        # Setup mock for get_by_id
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
        """Test updating therapy when session not found."""
        repository.get_by_id = AsyncMock(return_value=None)
        
        result = await repository.update_therapy(
            session_id=999,
            therapy_type="therapy",
        )
        
        assert result is None

    async def test_acquire_lock_different_session_ids(self, repository, mock_session):
        """Test that different session IDs get different lock keys."""
        for session_id in [1, 42, 999, 1000000]:
            mock_session.execute.reset_mock()
            
            await repository.acquire_session_lock(session_id)
            
            call_args = mock_session.execute.call_args
            # Parameters passed as second positional argument or kwargs
            params = call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs
            assert params == {"lock_key": session_id}

    async def test_update_flow_phase(self, repository):
        """Test flow phase update in session."""
        mock_db_session = MagicMock(spec=TherapySession)
        repository.get_by_id = AsyncMock(return_value=mock_db_session)
        repository.update = AsyncMock(return_value=mock_db_session)

        result = await repository.update_flow_phase(session_id=1, flow_phase="intake")

        assert result == mock_db_session
        repository.update.assert_called_once_with(mock_db_session, flow_phase="intake")

    async def test_increment_intake_turns(self, repository):
        """Test intake turns increment."""
        mock_db_session = MagicMock(spec=TherapySession)
        mock_db_session.intake_user_turns = 3
        repository.get_by_id = AsyncMock(return_value=mock_db_session)
        repository.update = AsyncMock(return_value=mock_db_session)

        await repository.increment_intake_turns(session_id=1)

        repository.update.assert_called_once_with(
            mock_db_session,
            intake_user_turns=4,
        )

    async def test_mark_intake_completed(self, repository):
        """Test intake completion marker updates phase and timestamp."""
        mock_db_session = MagicMock(spec=TherapySession)
        repository.get_by_id = AsyncMock(return_value=mock_db_session)
        repository.update = AsyncMock(return_value=mock_db_session)

        await repository.mark_intake_completed(session_id=1)

        call_args = repository.update.call_args
        assert call_args.kwargs["flow_phase"] == "therapy"
        assert call_args.kwargs["intake_completed_at"] is not None
