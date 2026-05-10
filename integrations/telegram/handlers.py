"""
Telegram message handlers for Opora.
"""

from typing import TYPE_CHECKING

from aiogram import types
from aiogram.filters import Command

from core.logging import get_logger, LogContexts
from integrations.telegram.bot import create_dispatcher
from integrations.telegram.prescreening import (
    check_and_handle_prescreening,
    is_in_prescreening,
    handle_prescreening_text,
)

if TYPE_CHECKING:
    from services.dialogue_service import DialogueService

logger = get_logger(LogContexts.TELEGRAM)
dispatcher = create_dispatcher()


@dispatcher.message(Command("start"))
async def cmd_start(message: types.Message, dialogue_service: DialogueService):
    """Handle /start command."""
    logger.info(
        "telegram_command_start",
        user_id=message.from_user.id,
        username=message.from_user.username,
    )
    
    # Check if prescreening is needed first
    prescreening_handled = await check_and_handle_prescreening(message)
    if prescreening_handled:
        logger.info("prescreening_initiated", user_id=message.from_user.id)
        return
    
    # User has completed prescreening - start normal session
    greeting = await dialogue_service.start_session(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
    )
    
    await message.answer(greeting)


@dispatcher.message(Command("summary"))
async def cmd_summary(message: types.Message, dialogue_service: DialogueService):
    """Return current patient card summary from DB without LLM."""
    logger.info(
        "telegram_command_summary",
        user_id=message.from_user.id,
    )
    summary_text = await dialogue_service.get_patient_summary(telegram_id=message.from_user.id)
    await message.answer(summary_text)


@dispatcher.message()
async def handle_message(message: types.Message, dialogue_service: DialogueService):
    """Handle regular text messages."""
    if not message.text:
        return
    
    logger.info(
        "telegram_message_received",
        user_id=message.from_user.id,
        message_len=len(message.text),
    )
    
    # Check if user is in prescreening flow
    if is_in_prescreening(message.from_user.id):
        handled = await handle_prescreening_text(message)
        if handled:
            return
    
    # Check if prescreening is needed (for users who haven't completed it)
    prescreening_needed = await check_and_handle_prescreening(message)
    if prescreening_needed:
        return
    
    # Normal dialogue flow
    result = await dialogue_service.process_message(
        telegram_id=message.from_user.id,
        text=message.text,
    )
    
    await message.answer(result["response"])
    
    if result.get("session_ended"):
        logger.info(
            "session_ended_by_agent",
            user_id=message.from_user.id,
        )
