"""Telegram integration for Opora."""

from .bot import create_bot, create_dispatcher, setup_bot_on_startup, setup_bot_commands
from .handlers import dispatcher
from .prescreening import (
    check_and_handle_prescreening,
    is_in_prescreening,
    handle_prescreening_text,
    start_prescreening,
    start_prescreening_for_edit,
    PrescreeningState,
    THERAPIST_STYLES,  # NEW: renamed from THERAPIST_TRAITS
    DEFAULT_THERAPIST_NAME,
    DEFAULT_THERAPIST_GENDER,
)

__all__ = [
    "create_bot",
    "create_dispatcher",
    "setup_bot_on_startup",
    "setup_bot_commands",
    "dispatcher",
    "check_and_handle_prescreening",
    "is_in_prescreening",
    "handle_prescreening_text",
    "start_prescreening",
    "start_prescreening_for_edit",
    "PrescreeningState",
    "THERAPIST_STYLES",  # NEW: renamed from THERAPIST_TRAITS
    "DEFAULT_THERAPIST_NAME",
    "DEFAULT_THERAPIST_GENDER",
]
