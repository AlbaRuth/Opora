"""
Agent execution log model for observability.
"""

from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .account import Account
    from .therapy_session import TherapySession


class AgentLog(Base, TimestampMixin):
    """Detailed log of agent LLM calls and reasoning."""

    __tablename__ = "agent_logs"
    __table_args__ = {"schema": "observability"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("identity.accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("therapy.therapy_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Agent identification
    agent_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # "therapist", "evaluator"
    task_name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # "generate_response", "assess_emotion", etc.

    # LLM configuration
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=150)

    # Request/Response
    trace_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    turn_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_messages: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Performance metrics
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_input: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Numeric(12, 8), nullable=True)

    # Outcome
    success: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Additional metadata (renamed to avoid SQLAlchemy reserved attribute conflict)
    extra_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True
    )
    provider_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship(
        back_populates="agent_logs", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<AgentLog(id={self.id}, agent={self.agent_type}, task={self.task_name})>"
