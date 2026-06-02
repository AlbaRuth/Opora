"""Chat browsing endpoints for Opora Monitor."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.channels import CHANNEL_TELEGRAM
from db.models import Account, Message, TherapySession, UserProfile
from db.repositories import ConversationTraceRepository, MessageRepository
from monitoring.api.deps import db_session, require_monitor_auth
from monitoring.api.schemas import ChatSummary, MessageItem, TraceSummary

router = APIRouter(
    prefix="/api/chats",
    tags=["chats"],
    dependencies=[Depends(require_monitor_auth)],
)


@router.get("", response_model=list[ChatSummary])
async def list_chats(
    source: str | None = Query(default=None, pattern="^(telegram|sandbox)$"),
    query: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(db_session),
) -> list[ChatSummary]:
    stmt = (
        select(TherapySession, Account, UserProfile)
        .join(Account, Account.id == TherapySession.account_id)
        .outerjoin(UserProfile, UserProfile.account_id == Account.id)
        .order_by(desc(TherapySession.updated_at))
        .limit(limit)
    )

    if source:
        stmt = stmt.where(Account.origin == source)

    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Account.username.ilike(pattern),
                Account.first_name.ilike(pattern),
                UserProfile.display_name.ilike(pattern),
            )
        )

    rows = (await session.execute(stmt)).all()
    return [
        ChatSummary(
            session_id=therapy_session.id,
            account_id=account.id,
            telegram_id=account.telegram_id,
            username=account.username,
            display_name=user_profile.effective_display_name if user_profile else account.first_name,
            source=account.origin or CHANNEL_TELEGRAM,
            session_number=therapy_session.session_number,
            therapy_type=therapy_session.therapy_type,
            is_active=therapy_session.is_active,
            dialog_count=therapy_session.dialog_count,
            created_at=therapy_session.created_at,
            updated_at=therapy_session.updated_at,
        )
        for therapy_session, account, user_profile in rows
    ]


@router.get("/{session_id}", response_model=ChatSummary)
async def get_chat(
    session_id: int,
    session: AsyncSession = Depends(db_session),
) -> ChatSummary:
    stmt = (
        select(TherapySession, Account, UserProfile)
        .join(Account, Account.id == TherapySession.account_id)
        .outerjoin(UserProfile, UserProfile.account_id == Account.id)
        .where(TherapySession.id == session_id)
    )
    row = (await session.execute(stmt)).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Chat not found")
    therapy_session, account, user_profile = row
    return ChatSummary(
        session_id=therapy_session.id,
        account_id=account.id,
        telegram_id=account.telegram_id,
        username=account.username,
        display_name=user_profile.effective_display_name if user_profile else account.first_name,
        source=account.origin or CHANNEL_TELEGRAM,
        session_number=therapy_session.session_number,
        therapy_type=therapy_session.therapy_type,
        is_active=therapy_session.is_active,
        dialog_count=therapy_session.dialog_count,
        created_at=therapy_session.created_at,
        updated_at=therapy_session.updated_at,
    )


@router.get("/{session_id}/messages", response_model=list[MessageItem])
async def get_chat_messages(
    session_id: int,
    session: AsyncSession = Depends(db_session),
) -> list[MessageItem]:
    repo = MessageRepository(session)
    messages = await repo.get_session_messages(session_id)
    return [_message_to_schema(message) for message in messages]


@router.get("/{session_id}/traces", response_model=list[TraceSummary])
async def get_chat_traces(
    session_id: int,
    session: AsyncSession = Depends(db_session),
) -> list[TraceSummary]:
    repo = ConversationTraceRepository(session)
    traces = await repo.get_session_traces(session_id)
    return [
        TraceSummary(
            trace_id=str(trace.trace_id),
            turn_id=str(trace.turn_id),
            session_id=trace.session_id,
            account_id=trace.account_id,
            channel=trace.channel,
            source=trace.source,
            status=trace.status,
            duration_ms=trace.duration_ms,
            llm_latency_ms=trace.llm_latency_ms,
            total_tokens_input=trace.total_tokens_input,
            total_tokens_output=trace.total_tokens_output,
            total_cost_usd=float(trace.total_cost_usd) if trace.total_cost_usd is not None else None,
            started_at=trace.started_at,
            finished_at=trace.finished_at,
            error_message=trace.error_message,
        )
        for trace in traces
    ]


def _message_to_schema(message: Message) -> MessageItem:
    return MessageItem(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        message_number=message.message_number,
        primary_emotion=message.primary_emotion,
        emotional_intensity=message.emotional_intensity,
        created_at=message.created_at,
    )
