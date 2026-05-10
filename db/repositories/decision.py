"""
Decision log repository for Opora.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import DecisionLog
from .base import BaseRepository


class DecisionLogRepository(BaseRepository[DecisionLog]):
    """Repository for DecisionLog operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, DecisionLog)
    
    async def log_decision(
        self,
        session_id: int,
        response_number: int,
        memory_invoke_result: str | None = None,
        is_rejecting: bool = False,
        current_therapy: str = "unspecified therapy",
        current_stage: str | None = None,
        primary_emotion: str | None = None,
        emotional_intensity: float | None = None,
        response_strategy: str | None = None,
        strategy_description: str | None = None,
        patient_attitude: str | None = None,
        decision_snapshot: dict[str, Any] | None = None,
    ) -> DecisionLog:
        """Log agent decision for response."""
        return await self.create(
            session_id=session_id,
            response_number=response_number,
            memory_invoke_result=memory_invoke_result,
            is_rejecting=is_rejecting,
            current_therapy=current_therapy,
            current_stage=current_stage,
            primary_emotion=primary_emotion,
            emotional_intensity=emotional_intensity,
            response_strategy=response_strategy,
            strategy_description=strategy_description,
            patient_attitude=patient_attitude,
            decision_snapshot=decision_snapshot,
        )
    
    async def get_session_decisions(
        self,
        session_id: int,
    ) -> list[DecisionLog]:
        """Get all decisions for session."""
        result = await self.session.execute(
            select(DecisionLog)
            .where(DecisionLog.session_id == session_id)
            .order_by(DecisionLog.response_number)
        )
        return result.scalars().all()
    
    async def get_latest_decision(self, session_id: int) -> DecisionLog | None:
        """Get latest decision for session."""
        result = await self.session.execute(
            select(DecisionLog)
            .where(DecisionLog.session_id == session_id)
            .order_by(DecisionLog.response_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_strategies_used_in_session(
        self,
        session_id: int,
    ) -> list[str]:
        """Get list of strategies used in session."""
        decisions = await self.get_session_decisions(session_id)
        strategies = [d.response_strategy for d in decisions if d.response_strategy]
        return strategies
