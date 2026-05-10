"""
Langfuse observability client for Opora.
Based on SupportAssistant patterns.
"""

from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncGenerator

from langfuse import Langfuse

from core.config import get_settings
from core.logging import get_logger, LogContexts

logger = get_logger(LogContexts.LANGFUSE)

# Context variable for current turn tracking
_turn_active: ContextVar[bool] = ContextVar("turn_active", default=False)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


class LangfuseClient:
    """Langfuse client with trace and generation tracking."""
    
    _instance: "LangfuseClient | None" = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.settings = get_settings()
        
        if not self.settings.langfuse_enabled:
            self.client = None
            self._initialized = True
            return
        
        try:
            self.client = Langfuse(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key,
                host=self.settings.langfuse_host,
            )
            logger.info("langfuse_initialized", host=self.settings.langfuse_host)
        except Exception as e:
            logger.error("langfuse_init_failed", error=str(e))
            self.client = None
        
        self._initialized = True
    
    def is_enabled(self) -> bool:
        """Check if Langfuse is enabled and initialized."""
        return self.client is not None
    
    def create_trace(
        self,
        name: str,
        user_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any | None:
        """Create a new trace."""
        if not self.is_enabled():
            return None
        
        try:
            trace = self.client.trace(
                name=name,
                user_id=user_id,
                session_id=session_id,
                metadata=metadata or {},
            )
            return trace
        except Exception as e:
            logger.warning("langfuse_trace_creation_failed", error=str(e))
            return None
    
    def create_generation(
        self,
        trace: Any,
        name: str,
        model: str,
        prompt: str | None = None,
        completion: str | None = None,
        usage: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any | None:
        """Create a generation within a trace."""
        if not self.is_enabled() or trace is None:
            return None
        
        try:
            generation = trace.generation(
                name=name,
                model=model,
                input=prompt,
                output=completion,
                usage=usage,
                metadata=metadata or {},
            )
            return generation
        except Exception as e:
            logger.warning("langfuse_generation_creation_failed", error=str(e))
            return None
    
    def update_trace(
        self,
        trace: Any,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update trace with output."""
        if not self.is_enabled() or trace is None:
            return
        
        try:
            trace.update(
                output=output,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.warning("langfuse_trace_update_failed", error=str(e))
    
    def flush(self) -> None:
        """Flush pending events to Langfuse."""
        if self.is_enabled():
            try:
                self.client.flush()
            except Exception as e:
                logger.warning("langfuse_flush_failed", error=str(e))


@asynccontextmanager
async def trace_scope(
    name: str,
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AsyncGenerator[Any, None]:
    """Context manager for Langfuse trace scope."""
    client = LangfuseClient()
    trace = client.create_trace(name, user_id, session_id, metadata)
    
    try:
        _turn_active.set(True)
        if trace:
            _trace_id.set(trace.id)
        yield trace
    finally:
        _turn_active.set(False)
        _trace_id.set(None)
        client.flush()


def get_current_trace_id() -> str | None:
    """Get current trace ID from context."""
    return _trace_id.get()


def is_trace_active() -> bool:
    """Check if trace scope is currently active."""
    return _turn_active.get()
