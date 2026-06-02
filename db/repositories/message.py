"""
Message repository for Opora.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from db.models import Message
from observability.tracing import get_current_trace

from .base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Repository for Message operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Message)
    
    async def create_message(
        self,
        session_id: int,
        role: str,
        content: str,
        message_number: int,
        primary_emotion: str | None = None,
        emotional_intensity: float | None = None,
        trace_id: str | None = None,
        channel: str | None = None,
    ) -> Message:
        """Create new message in session."""
        current_trace = get_current_trace()
        if current_trace:
            trace_id = trace_id or str(current_trace.trace_id)
            channel = channel or current_trace.channel
        return await self.create(
            session_id=session_id,
            role=role,
            content=content,
            message_number=message_number,
            trace_id=trace_id,
            channel=channel or "telegram",
            primary_emotion=primary_emotion,
            emotional_intensity=emotional_intensity,
        )
    
    async def get_session_messages(
        self,
        session_id: int,
        limit: int | None = None,
    ) -> list[Message]:
        """Get messages for session."""
        query = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.message_number)
        )
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_latest_messages(
        self,
        session_id: int,
        count: int = 10,
    ) -> list[Message]:
        """Get latest N messages for session."""
        result = await self.session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(desc(Message.message_number))
            .limit(count)
        )
        # Reverse to get chronological order
        messages = result.scalars().all()
        return list(reversed(messages))
    
    async def get_message_count(self, session_id: int) -> int:
        """Get total message count for session."""
        result = await self.session.execute(
            select(Message)
            .where(Message.session_id == session_id)
        )
        return len(result.scalars().all())

    async def get_recent_messages(
        self,
        session_id: int,
        limit: int = 10,
    ) -> list[Message]:
        """Get recent messages for session (alias for get_latest_messages)."""
        return await self.get_latest_messages(session_id, count=limit)
