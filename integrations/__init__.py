"""Integrations module for Opora."""

from .openrouter import OpenRouterClient
from .telegram import create_bot, create_dispatcher, setup_bot_on_startup, dispatcher

__all__ = [
    "OpenRouterClient",
    "create_bot",
    "create_dispatcher",
    "setup_bot_on_startup",
    "dispatcher",
]
