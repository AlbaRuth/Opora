"""
Agent log repository for Opora.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from db.models import AgentLog
from .base import BaseRepository


class AgentLogRepository(BaseRepository[AgentLog]):
    """Repository for AgentLog operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, AgentLog)
    
    async def log_llm_call(
        self,
        user_id: int,
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
        langfuse_trace_id: str | None = None,
        langfuse_generation_id: str | None = None,
        session_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentLog:
        """Log LLM agent execution."""
        return await self.create(
            user_id=user_id,
            session_id=session_id,
            agent_type=agent_type,
            task_name=task_name,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt=prompt,
            response=response,
            reasoning=reasoning,
            latency_ms=latency_ms,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            success=success,
            error_message=error_message,
            langfuse_trace_id=langfuse_trace_id,
            langfuse_generation_id=langfuse_generation_id,
            extra_metadata=metadata,
        )
    
    async def get_user_logs(
        self,
        user_id: int,
        limit: int = 100,
    ) -> list[AgentLog]:
        """Get agent logs for user."""
        result = await self.session.execute(
            select(AgentLog)
            .where(AgentLog.user_id == user_id)
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
    
    async def get_task_logs(
        self,
        user_id: int,
        task_name: str,
        limit: int = 50,
    ) -> list[AgentLog]:
        """Get logs for specific task."""
        result = await self.session.execute(
            select(AgentLog)
            .where(AgentLog.user_id == user_id)
            .where(AgentLog.task_name == task_name)
            .order_by(desc(AgentLog.created_at))
            .limit(limit)
        )
        return result.scalars().all()
