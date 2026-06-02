"""
Agent log repository for Opora.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from db.models import AgentLog
from observability.tracing import get_current_trace
from .base import BaseRepository


class AgentLogRepository(BaseRepository[AgentLog]):
    """Repository for AgentLog operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, AgentLog)

    async def log_llm_call(
        self,
        account_id: int,
        agent_type: str,
        task_name: str,
        model: str,
        temperature: float,
        max_tokens: int,
        prompt: str | None = None,
        response: str | None = None,
        reasoning: str | None = None,
        latency_ms: int | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        success: bool = True,
        error_message: str | None = None,
        session_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        prompt_messages: list[dict[str, Any]] | None = None,
        reasoning_summary: str | None = None,
        cost_usd: float | None = None,
        provider_metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
        turn_id: str | None = None,
        channel: str | None = None,
    ) -> AgentLog:
        """Log LLM agent execution."""
        current_trace = get_current_trace()
        if current_trace:
            current_trace.add_usage(
                prompt_tokens=tokens_input,
                completion_tokens=tokens_output,
                latency_ms=latency_ms,
            )
            current_trace.add_cost(cost_usd)
            trace_id = trace_id or str(current_trace.trace_id)
            turn_id = turn_id or str(current_trace.turn_id)
            channel = channel or current_trace.channel
            session_id = session_id or current_trace.session_id

        return await self.create(
            account_id=account_id,
            session_id=session_id,
            trace_id=trace_id,
            turn_id=turn_id,
            channel=channel,
            agent_type=agent_type,
            task_name=task_name,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt=prompt,
            prompt_messages=prompt_messages,
            response=response,
            reasoning=reasoning,
            reasoning_summary=reasoning_summary,
            latency_ms=latency_ms,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
            success=success,
            error_message=error_message,
            extra_metadata=metadata,
            provider_metadata=provider_metadata,
        )

    async def get_account_logs(
        self,
        account_id: int,
        limit: int = 100,
    ) -> list[AgentLog]:
        """Get agent logs for account."""
        result = await self.session.execute(
            select(AgentLog)
            .where(AgentLog.account_id == account_id)
            .order_by(desc(AgentLog.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_session_logs(
        self,
        session_id: int,
    ) -> list[AgentLog]:
        """Get agent logs for session."""
        result = await self.session.execute(
            select(AgentLog)
            .where(AgentLog.session_id == session_id)
            .order_by(AgentLog.created_at)
        )
        return result.scalars().all()

    async def get_trace_logs(self, trace_id: str) -> list[AgentLog]:
        """Get agent logs for one end-to-end trace."""
        result = await self.session.execute(
            select(AgentLog)
            .where(AgentLog.trace_id == trace_id)
            .order_by(AgentLog.created_at)
        )
        return result.scalars().all()

    async def get_task_logs(
        self,
        account_id: int,
        task_name: str,
        limit: int = 50,
    ) -> list[AgentLog]:
        """Get logs for specific task."""
        result = await self.session.execute(
            select(AgentLog)
            .where(AgentLog.account_id == account_id)
            .where(AgentLog.task_name == task_name)
            .order_by(desc(AgentLog.created_at))
            .limit(limit)
        )
        return result.scalars().all()
