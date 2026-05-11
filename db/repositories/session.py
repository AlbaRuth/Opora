"""
Therapy session repository for Opora.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, text

from db.models import TherapySession
from .base import BaseRepository


class SessionRepository(BaseRepository[TherapySession]):
    """Repository for TherapySession operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, TherapySession)

    async def get_active_session(self, account_id: int) -> TherapySession | None:
        """Get active session for account."""
        result = await self.session.execute(
            select(TherapySession)
            .where(TherapySession.account_id == account_id)
            .where(TherapySession.is_active == True)
            .order_by(desc(TherapySession.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_session(self, account_id: int) -> TherapySession | None:
        """Get latest session for account (active or not)."""
        result = await self.session.execute(
            select(TherapySession)
            .where(TherapySession.account_id == account_id)
            .order_by(desc(TherapySession.session_number))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_session(
        self,
        account_id: int,
        session_number: int,
        therapy_type: str = "unspecified therapy",
        therapy_reason: str | None = None,
    ) -> TherapySession:
        """Create new therapy session."""
        return await self.create(
            account_id=account_id,
            session_number=session_number,
            therapy_type=therapy_type,
            therapy_reason=therapy_reason,
            is_active=True,
            dialog_count=0,
        )

    async def end_session(self, session_id: int) -> TherapySession | None:
        """Mark session as ended."""
        session = await self.get_by_id(session_id)
        if not session:
            return None

        return await self.update(
            session,
            is_active=False,
            ended_at=datetime.utcnow(),
        )

    async def increment_dialog_count(self, session_id: int) -> TherapySession | None:
        """Increment dialog count for session."""
        session = await self.get_by_id(session_id)
        if not session:
            return None

        return await self.update(
            session,
            dialog_count=session.dialog_count + 1,
        )

    async def update_current_stage(
        self,
        session_id: int,
        stage: str,
    ) -> TherapySession | None:
        """Update current stage assessment."""
        session = await self.get_by_id(session_id)
        if not session:
            return None

        return await self.update(session, current_stage=stage)

    async def update_therapy(
        self,
        session_id: int,
        therapy_type: str,
        therapy_reason: str | None = None,
    ) -> TherapySession | None:
        """Update therapy metadata for a session."""
        session = await self.get_by_id(session_id)
        if not session:
            return None

        return await self.update(
            session,
            therapy_type=therapy_type,
            therapy_reason=therapy_reason,
        )

    async def acquire_session_lock(self, session_id: int) -> None:
        """
        Acquire transaction-scoped PostgreSQL advisory lock for session.

        Lock is automatically released on transaction commit/rollback.
        """
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": int(session_id)},
        )

    async def get_all_account_sessions(self, account_id: int) -> list[TherapySession]:
        """Get all sessions for account ordered by session number."""
        result = await self.session.execute(
            select(TherapySession)
            .where(TherapySession.account_id == account_id)
            .order_by(TherapySession.session_number)
        )
        return result.scalars().all()
