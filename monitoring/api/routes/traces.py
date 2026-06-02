"""Trace detail endpoints for Opora Monitor."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentLog
from db.repositories import AgentLogRepository, ConversationTraceRepository
from monitoring.api.deps import db_session, require_monitor_auth
from monitoring.api.schemas import LlmCallItem, TraceDetail, TraceSummary

router = APIRouter(
    prefix="/api/traces",
    tags=["traces"],
    dependencies=[Depends(require_monitor_auth)],
)


@router.get("/{trace_id}", response_model=TraceDetail)
async def get_trace_detail(
    trace_id: str,
    session: AsyncSession = Depends(db_session),
) -> TraceDetail:
    trace_repo = ConversationTraceRepository(session)
    trace = await trace_repo.get_by_trace_id(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    log_repo = AgentLogRepository(session)
    logs = await log_repo.get_trace_logs(trace_id)

    return TraceDetail(
        trace=TraceSummary(
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
        ),
        llm_calls=[_log_to_schema(log) for log in logs],
    )


def _log_to_schema(log: AgentLog) -> LlmCallItem:
    return LlmCallItem(
        id=log.id,
        agent_type=log.agent_type,
        task_name=log.task_name,
        model=log.model,
        temperature=log.temperature,
        max_tokens=log.max_tokens,
        prompt=log.prompt,
        prompt_messages=log.prompt_messages,
        prompt_messages_full=log.prompt_messages_full,
        response=log.response,
        response_full=log.response_full,
        prompt_truncated=log.prompt_truncated,
        response_truncated=log.response_truncated,
        reasoning=log.reasoning,
        reasoning_summary=log.reasoning_summary,
        latency_ms=log.latency_ms,
        tokens_input=log.tokens_input,
        tokens_output=log.tokens_output,
        cost_usd=float(log.cost_usd) if log.cost_usd is not None else None,
        success=log.success,
        error_message=log.error_message,
        metadata=log.extra_metadata,
        provider_metadata=log.provider_metadata,
        channel=log.channel,
        source=log.source,
        sandbox_run_id=log.sandbox_run_id,
        sandbox_batch_id=log.sandbox_batch_id,
        created_at=log.created_at,
    )
