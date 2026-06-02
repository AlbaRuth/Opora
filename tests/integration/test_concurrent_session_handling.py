"""Integration tests for concurrent session handling with DB lock."""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Tuple

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Account, TherapySession
from db.repositories import AccountRepository, SessionRepository
from tests.factories import create_active_therapy_session

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root / "agents" / "core"))
from session_state import SessionState  # noqa: E402

sys.path.pop(0)


@pytest.mark.skipif(
    not os.environ.get("OPORA_RUN_INTEGRATION"),
    reason="Set OPORA_RUN_INTEGRATION=1 to run (uses real PostgreSQL + non-rolled-back semantics).",
)
class TestConcurrentSessionHandling:
    """
    Integration tests verifying per-session lock and state consistency.
    
    These tests verify that:
    1. Concurrent messages to same session are serialized
    2. State counters don't drift under concurrent load
    3. DB remains consistent after concurrent operations
    """

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> Account:
        repo = AccountRepository(db_session)
        return await repo.create_from_telegram(
            telegram_id=999999,
            username="test_user",
        )

    @pytest_asyncio.fixture
    async def test_session(
        self, db_session: AsyncSession, test_user: Account
    ) -> TherapySession:
        ts, _ = await create_active_therapy_session(
            db_session, test_user.id, flow_phase="therapy"
        )
        return ts

    async def test_concurrent_dialog_count_increment(
        self,
        db_session: AsyncSession,
        test_session: TherapySession,
    ):
        session_repo = SessionRepository(db_session)
        session_id = test_session.id

        async def increment_dialog() -> int:
            await session_repo.acquire_session_lock(session_id)
            await session_repo.increment_dialog_count(session_id)
            sess = await session_repo.get_by_id(session_id)
            return sess.dialog_count if sess else -1

        tasks = [increment_dialog() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Concurrent increments raised errors: {errors}"

        final_session = await session_repo.get_by_id(session_id)
        assert final_session.dialog_count == 5

    async def test_session_state_consistency_under_load(
        self,
        db_session: AsyncSession,
        test_user: Account,
    ):
        session_repo = SessionRepository(db_session)

        ts, _ = await create_active_therapy_session(
            db_session, test_user.id, flow_phase="therapy", session_number=2
        )
        ts.therapy_type = "initial therapy"
        ts.current_stage = "assessment"
        await db_session.flush()
        session = ts

        async def simulate_message_processing(message_num: int) -> Tuple[int, str]:
            await session_repo.acquire_session_lock(session.id)
            db_session_obj = await session_repo.get_by_id(session.id)
            state = SessionState(
                patient_id=str(test_user.id),
                session_id=f"{test_user.id}_{db_session_obj.session_number}",
                session_db_id=db_session_obj.id,
                dialog_count=db_session_obj.dialog_count,
                session_counter=db_session_obj.session_number,
                current_therapy=db_session_obj.therapy_type,
                current_stage=db_session_obj.current_stage or "",
            )
            state.dialog_count += 1
            state.current_stage = f"stage_{message_num}"
            await session_repo.increment_dialog_count(session.id)
            await session_repo.update_current_stage(session.id, state.current_stage)
            return state.dialog_count, state.current_stage

        message_count = 10
        tasks = [simulate_message_processing(i) for i in range(message_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_results: List[Tuple[int, str]] = [
            r for r in results if not isinstance(r, Exception)
        ]
        errors = [r for r in results if isinstance(r, Exception)]

        assert len(errors) == 0, f"Some concurrent operations failed: {errors}"
        assert len(successful_results) == message_count

        final_session = await session_repo.get_by_id(session.id)
        assert final_session.dialog_count == message_count


class TestSessionStateMapping:
    """Test mapping between DB models and SessionState DTO."""

    def test_state_from_db_session(self):
        """Test creating SessionState from simulated DB session data."""
        # Simulating what DialogueService does
        db_data = {
            "user_id": 100,
            "id": 50,
            "session_number": 3,
            "dialog_count": 10,
            "therapy_type": "mindfulness-based therapy",
            "current_stage": "working_through",
        }

        state = SessionState(
            patient_id=str(db_data["user_id"]),
            session_id=f"{db_data['user_id']}_{db_data['session_number']}",
            session_db_id=db_data["id"],
            dialog_count=db_data["dialog_count"],
            session_counter=db_data["session_number"],
            current_therapy=db_data["therapy_type"],
            current_stage=db_data["current_stage"] or "",
        )

        assert state.patient_id == "100"
        assert state.session_db_id == 50
        assert state.session_counter == 3
        assert state.current_therapy == "mindfulness-based therapy"

    def test_state_roundtrip_simulation(self):
        """Simulate the full roundtrip: DB -> State -> Agent -> State -> DB."""
        # Initial DB state
        initial_state = SessionState(
            patient_id="42",
            session_id="42_5",
            session_db_id=100,
            dialog_count=3,
            session_counter=5,
            current_therapy="cognitive-behavioral therapy",
            current_stage="assessment",
        )

        # Agent processing mutates state
        initial_state.dialog_count += 1
        initial_state.current_therapy = "updated therapy"
        initial_state.current_stage = "intervention"

        # Verify mutations
        assert initial_state.dialog_count == 4
        assert initial_state.current_therapy == "updated therapy"
        assert initial_state.current_stage == "intervention"
