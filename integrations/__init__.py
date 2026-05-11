"""Integrations module for Opora."""

from .openrouter import OpenRouterClient
from .telegram import create_bot, create_dispatcher, setup_bot_on_startup, dispatcher
from .langfuse import (
    LangfuseClient,
    init_langfuse_on_startup,
    trace_scope,
    get_current_trace_id,
    is_trace_active,
)

__all__ = [
    "OpenRouterClient",
    "create_bot",
    "create_dispatcher",
    "setup_bot_on_startup",
    "dispatcher",
    "LangfuseClient",
    "init_langfuse_on_startup",
    "trace_scope",
    "get_current_trace_id",
    "is_trace_active",
]
