"""Repository for end-to-end conversation traces."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import ConversationTrace
from observability.tracing import TraceContext

from .base import BaseRepository


class ConversationTraceRepository(BaseRepository[ConversationTrace]):
    """Persistence for one user-visible turn trace."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ConversationTrace)

    async def create_from_context(
        self,
        *,
        trace: TraceContext,
        status: str,
        finished_at: datetime,
        duration_ms: int,
        error_message: str | None = None,
    ) -> ConversationTrace:
        return await self.create(
            trace_id=str(trace.trace_id),
            turn_id=str(trace.turn_id),
            account_id=trace.account_id,
            session_id=trace.session_id,
            channel=trace.channel,
            source=trace.source,
            sandbox_run_id=trace.sandbox_run_id,
            sandbox_batch_id=trace.sandbox_batch_id,
            status=status,
            started_at=trace.started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            llm_latency_ms=trace.llm_latency_ms,
            total_tokens_input=trace.total_tokens_input,
            total_tokens_output=trace.total_tokens_output,
            total_cost_usd=trace.total_cost_usd or None,
            error_message=error_message,
        )

    async def get_by_trace_id(self, trace_id: str) -> ConversationTrace | None:
        result = await self.session.execute(
            select(ConversationTrace).where(ConversationTrace.trace_id == trace_id)
        )
        return result.scalar_one_or_none()

    async def get_session_traces(self, session_id: int) -> list[ConversationTrace]:
        result = await self.session.execute(
            select(ConversationTrace)
            .where(ConversationTrace.session_id == session_id)
            .order_by(ConversationTrace.started_at)
        )
        return result.scalars().all()

    async def list_recent(
        self,
        *,
        channel: str | None = None,
        limit: int = 100,
    ) -> list[ConversationTrace]:
        query = select(ConversationTrace).order_by(desc(ConversationTrace.started_at))
        if channel:
            query = query.where(ConversationTrace.channel == channel)
        result = await self.session.execute(query.limit(limit))
        return result.scalars().all()
