"""
Intake State repository for Opora.
Handles therapy.intake_states operations.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import IntakeState


class IntakeStateRepository:
    """Repository for IntakeState operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_session_id(self, session_id: int) -> IntakeState | None:
        """Get intake state by session ID."""
        result = await self.session.execute(
            select(IntakeState).where(IntakeState.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def create_for_session(
        self,
        session_id: int,
        flow_phase: str = "prescreening",
    ) -> IntakeState:
        """Create intake state for a session."""
        state = IntakeState(
            session_id=session_id,
            flow_phase=flow_phase,
            user_turn_count=0,
        )
        self.session.add(state)
        await self.session.flush()
        return state

    async def update_flow_phase(
        self,
        session_id: int,
        flow_phase: str,
    ) -> IntakeState | None:
        """Update flow phase for session."""
        state = await self.get_by_session_id(session_id)
        if not state:
            return None

        state.flow_phase = flow_phase
        await self.session.flush()
        return state

    async def increment_turns(self, session_id: int) -> IntakeState | None:
        """Increment user turn count."""
        state = await self.get_by_session_id(session_id)
        if not state:
            return None

        state.user_turn_count += 1
        await self.session.flush()
        return state

    async def mark_completed(self, session_id: int) -> IntakeState | None:
        """Mark intake as completed and switch to therapy phase."""
        state = await self.get_by_session_id(session_id)
        if not state:
            return None

        state.flow_phase = "therapy"
        state.completed_at = datetime.utcnow()
        await self.session.flush()
        return state

    async def is_intake_completed(self, session_id: int) -> bool:
        """Check if intake is completed for session."""
        state = await self.get_by_session_id(session_id)
        if not state:
            return False
        return state.is_intake_completed
