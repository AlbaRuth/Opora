"""Request-scoped trace context for chat observability."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import UUID, uuid4


_current_trace: ContextVar["TraceContext | None"] = ContextVar(
    "opora_current_trace",
    default=None,
)


@dataclass(slots=True)
class TraceContext:
    """Mutable trace state for one user-visible turn."""

    channel: str
    source: str
    trace_id: UUID = field(default_factory=uuid4)
    turn_id: UUID = field(default_factory=uuid4)
    account_id: int | None = None
    session_id: int | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    llm_latency_ms: int = 0
    total_cost_usd: float = 0.0

    def add_usage(
        self,
        *,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        latency_ms: int | None,
    ) -> None:
        """Accumulate model usage for end-to-end trace totals."""

        self.total_tokens_input += int(prompt_tokens or 0)
        self.total_tokens_output += int(completion_tokens or 0)
        self.llm_latency_ms += int(latency_ms or 0)

    def add_cost(self, cost_usd: float | None) -> None:
        """Accumulate provider cost for trace totals when available."""

        self.total_cost_usd += float(cost_usd or 0.0)


def get_current_trace() -> TraceContext | None:
    """Return active trace context, if this call stack has one."""

    return _current_trace.get()


@contextmanager
def trace_scope(trace: TraceContext) -> Iterator[TraceContext]:
    """Make trace context available to nested service and repository calls."""

    token = _current_trace.set(trace)
    try:
        yield trace
    finally:
        _current_trace.reset(token)


def serialize_prompt_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize provider messages for JSON storage without mutating input."""

    serialized: list[dict[str, str]] = []
    for message in messages:
        serialized.append(
            {
                "role": str(message.get("role", "")),
                "content": str(message.get("content", "")),
            }
        )
    return serialized
