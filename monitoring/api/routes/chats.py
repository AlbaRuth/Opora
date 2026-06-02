"""Chat browsing endpoints for Opora Monitor."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.channels import CHANNEL_TELEGRAM
from db.models import Account, Message, TherapySession, UserProfile
from db.repositories import AgentLogRepository, ConversationTraceRepository, MessageRepository
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
            sandbox_run_id=trace.sandbox_run_id,
            sandbox_batch_id=trace.sandbox_batch_id,
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


@router.get("/{session_id}/export")
async def export_chat(
    session_id: int,
    format: str = Query(default="json", pattern="^(json|md)$"),
    session: AsyncSession = Depends(db_session),
):
    chat = await get_chat(session_id, session)
    messages = await get_chat_messages(session_id, session)
    traces = await get_chat_traces(session_id, session)
    log_repo = AgentLogRepository(session)
    llm_calls = []
    for trace in traces:
        logs = await log_repo.get_trace_logs(trace.trace_id)
        llm_calls.extend(
            {
                "id": log.id,
                "trace_id": str(log.trace_id) if log.trace_id else None,
                "channel": log.channel,
                "source": log.source,
                "sandbox_run_id": log.sandbox_run_id,
                "sandbox_batch_id": log.sandbox_batch_id,
                "agent_type": log.agent_type,
                "task_name": log.task_name,
                "model": log.model,
                "prompt_messages": log.prompt_messages_full or log.prompt_messages,
                "response": log.response_full or log.response,
                "latency_ms": log.latency_ms,
                "tokens_input": log.tokens_input,
                "tokens_output": log.tokens_output,
                "success": log.success,
                "error_message": log.error_message,
                "metadata": log.extra_metadata,
                "provider_metadata": log.provider_metadata,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        )
    payload = {
        "chat": chat.model_dump(mode="json"),
        "messages": [message.model_dump(mode="json") for message in messages],
        "traces": [trace.model_dump(mode="json") for trace in traces],
        "llm_calls": llm_calls,
    }
    if format == "json":
        return payload
    return Response(
        content=_chat_export_markdown(payload),
        media_type="text/markdown; charset=utf-8",
    )


def _message_to_schema(message: Message) -> MessageItem:
    return MessageItem(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        message_number=message.message_number,
        channel=message.channel,
        primary_emotion=message.primary_emotion,
        emotional_intensity=message.emotional_intensity,
        created_at=message.created_at,
    )


def _chat_export_markdown(payload: dict) -> str:
    chat = payload["chat"]
    lines = [
        f"# Chat export: session {chat['session_id']}",
        "",
        f"- source: {chat['source']}",
        f"- account_id: {chat['account_id']}",
        f"- active: {chat['is_active']}",
        "",
        "## Transcript",
    ]
    for message in payload["messages"]:
        lines.extend(
            [
                "",
                f"### {message['message_number']}. {message['role']} ({message.get('channel', 'telegram')})",
                message["content"],
            ]
        )
    lines.extend(["", "## LLM Calls"])
    for call in payload["llm_calls"]:
        lines.extend(
            [
                "",
                f"### {call['agent_type']}.{call['task_name']}",
                f"- trace_id: {call['trace_id']}",
                f"- source: {call.get('channel')}/{call.get('source')}",
                f"- model: {call['model']}",
                f"- latency_ms: {call.get('latency_ms')}",
                "",
                "Response:",
                "```",
                call.get("response") or "",
                "```",
            ]
        )
    return "\n".join(lines)
