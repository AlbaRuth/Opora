"""Telegram integration for Opora."""

from .bot import create_bot, create_dispatcher, setup_bot_on_startup, setup_bot_commands
from .handlers import dispatcher
from .prescreening import (
    check_and_handle_prescreening,
    clear_prescreening_state,
    is_in_prescreening,
    handle_prescreening_text,
    start_prescreening,
    start_prescreening_for_edit,
)
from .prescreening_state import PrescreeningWizardState
from core.profile_labels import (
    DEFAULT_THERAPIST_GENDER,
    DEFAULT_THERAPIST_NAME,
    THERAPIST_STYLES,
)

__all__ = [
    "create_bot",
    "create_dispatcher",
    "setup_bot_on_startup",
    "setup_bot_commands",
    "dispatcher",
    "check_and_handle_prescreening",
    "clear_prescreening_state",
    "is_in_prescreening",
    "handle_prescreening_text",
    "start_prescreening",
    "start_prescreening_for_edit",
    "PrescreeningWizardState",
    "THERAPIST_STYLES",
    "DEFAULT_THERAPIST_NAME",
    "DEFAULT_THERAPIST_GENDER",
]
