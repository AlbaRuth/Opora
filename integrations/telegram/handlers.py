"""
Telegram message handlers for Opora.
"""

import time
from typing import TYPE_CHECKING

from aiogram import types
from aiogram.filters import Command

from core.logging import get_logger, LogContexts
from db.session import get_db_session
from integrations.telegram.bot import dispatcher
from integrations.telegram.prescreening import (
    check_and_handle_prescreening,
    is_in_prescreening,
    handle_prescreening_text,
    start_prescreening,
)

if TYPE_CHECKING:
    from services.dialogue_service import DialogueService

logger = get_logger(LogContexts.TELEGRAM)

# Latency budget for non-LLM operations (ms)
NON_LLM_LATENCY_BUDGET_MS = 500


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

    # Fallback for None greeting - should not happen but protects against crashes
    if greeting is None:
        logger.warning("start_session_returned_none", user_id=message.from_user.id)
        greeting = "Добро пожаловать! Нажмите /start чтобы начать сессию."

    await message.answer(greeting)


@dispatcher.message(Command("summary"))
async def cmd_summary(message: types.Message, dialogue_service: DialogueService):
    """Return current patient card summary from DB without LLM."""
    start_time = time.time()
    logger.info(
        "telegram_command_summary",
        user_id=message.from_user.id,
    )
    summary_text = await dialogue_service.get_patient_summary(telegram_id=message.from_user.id)
    await message.answer(summary_text)

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info("summary_command_finished", user_id=message.from_user.id, duration_ms=duration_ms)
    if duration_ms > NON_LLM_LATENCY_BUDGET_MS:
        logger.warning("summary_command_slow", user_id=message.from_user.id, duration_ms=duration_ms, budget_ms=NON_LLM_LATENCY_BUDGET_MS)


@dispatcher.message(Command("anket"))
async def cmd_anket(message: types.Message, dialogue_service: DialogueService):
    """Show user profile/anket with option to edit."""
    start_time = time.time()
    logger.info(
        "telegram_command_anket",
        user_id=message.from_user.id,
    )

    # Check if prescreening is needed first
    prescreening_handled = await check_and_handle_prescreening(message)
    if prescreening_handled:
        logger.info("anket_prescreening_required", user_id=message.from_user.id)
        return

    # User has completed prescreening - show anket
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    anket_text = await dialogue_service.get_user_anket(telegram_id=message.from_user.id)

    # Add edit button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Редактировать анкету", callback_data="anket:edit")]
    ])

    await message.answer(anket_text, reply_markup=keyboard)

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info("anket_command_finished", user_id=message.from_user.id, duration_ms=duration_ms)
    if duration_ms > NON_LLM_LATENCY_BUDGET_MS:
        logger.warning("anket_command_slow", user_id=message.from_user.id, duration_ms=duration_ms, budget_ms=NON_LLM_LATENCY_BUDGET_MS)


@dispatcher.message(Command("reset"))
async def cmd_reset(message: types.Message, dialogue_service: DialogueService):
    """Handle /reset command - initiate data deletion flow with confirmation."""
    logger.info(
        "telegram_command_reset",
        user_id=message.from_user.id,
    )

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    # Step 1: Show description with initial reset button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Очистить информацию обо мне", callback_data="reset:confirm_open")]
    ])

    await message.answer(
        "<b>Сброс данных</b>\n\n"
        "Это действие полностью удалит все ваши данные из системы, включ:\n"
        "• Анкету и настройки психолога\n"
        "• Историю сессий и сообщений\n"
        "• Клиническую карточку\n\n"
        "После удаления вы сможете начать с чистого листа через /start",
        reply_markup=keyboard,
    )


@dispatcher.callback_query(lambda c: c.data == "reset:confirm_open")
async def on_reset_confirm_open(callback: types.CallbackQuery):
    """Handle initial reset button - show confirmation with Yes/No options."""
    logger.info(
        "reset_confirmation_opened",
        user_id=callback.from_user.id,
    )

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    # Edit the same message to show confirmation warning
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data="reset:confirm_yes"),
            InlineKeyboardButton(text="❌ Нет, отменить", callback_data="reset:confirm_no"),
        ]
    ])

    try:
        await callback.message.edit_text(
            "<b>⚠️ Вы уверены?</b>\n\n"
            "Это действие <b>необратимо</b>. Все данные будут безвозвратно удалены.",
            reply_markup=keyboard,
        )
        await callback.answer()
    except Exception as e:
        logger.warning("reset_confirm_edit_failed", user_id=callback.from_user.id, error=str(e))
        await callback.answer("Ошибка обновления сообщения")


@dispatcher.callback_query(lambda c: c.data == "reset:confirm_no")
async def on_reset_confirm_no(callback: types.CallbackQuery):
    """Handle No button - cancel reset and show cancellation message."""
    logger.info(
        "reset_cancelled_by_user",
        user_id=callback.from_user.id,
    )

    try:
        await callback.message.edit_text(
            "✅ <b>Отменено</b>\n\n"
            "Ваши данные не были удалены. Вы можете продолжать использовать бота."
        )
        await callback.answer("Отменено")
    except Exception as e:
        logger.warning("reset_cancel_edit_failed", user_id=callback.from_user.id, error=str(e))
        await callback.answer("Отменено")


@dispatcher.callback_query(lambda c: c.data == "reset:confirm_yes")
async def on_reset_confirm_yes(callback: types.CallbackQuery, dialogue_service: DialogueService):
    """Handle Yes button - delete all user data and show success message."""
    user_id = callback.from_user.id
    logger.info(
        "reset_confirmed_by_user",
        user_id=user_id,
    )

    # Clear prescreening in-memory state before DB deletion
    from integrations.telegram.prescreening import clear_prescreening_state
    clear_prescreening_state(user_id)

    # Delete all user data from database
    deleted = await dialogue_service.reset_user_data(telegram_id=user_id)

    try:
        if deleted:
            await callback.message.edit_text(
                "🗑 <b>Данные удалены</b>\n\n"
                "Вся информация о вас была полностью удалена из системы.\n\n"
                "Нажмите /start, чтобы начать новую настройку профиля."
            )
            logger.info("reset_completed_successfully", user_id=user_id)
        else:
            await callback.message.edit_text(
                "ℹ️ <b>Нет данных для удаления</b>\n\n"
                "Ваши данные уже были удалены ранее или не существовали.\n\n"
                "Нажмите /start, чтобы начать настройку профиля."
            )
            logger.info("reset_no_data_found", user_id=user_id)
        await callback.answer("Готово")
    except Exception as e:
        logger.warning("reset_success_edit_failed", user_id=user_id, error=str(e))
        await callback.answer("Готово")


@dispatcher.callback_query(lambda c: c.data == "anket:edit")
async def on_anket_edit(callback: types.CallbackQuery):
    """Handle anket edit button click."""
    logger.info(
        "anket_edit_started",
        user_id=callback.from_user.id,
    )
    await callback.answer("Начинаем редактирование анкеты...")

    # Start prescreening in edit mode
    from integrations.telegram.prescreening import start_prescreening_for_edit
    await start_prescreening_for_edit(callback.message, callback.from_user.id)


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

    # Check if user is in prescreening flow first
    if is_in_prescreening(message.from_user.id):
        handled = await handle_prescreening_text(message)
        if handled:
            return

    # Check if prescreening is needed - unified guard (using new schema)
    async with get_db_session() as session:
        from db.repositories import AccountRepository, TherapistPreferenceRepository
        account_repo = AccountRepository(session)
        pref_repo = TherapistPreferenceRepository(session)

        account = await account_repo.get_by_telegram_id(message.from_user.id)

        if not account:
            # New user - start prescreening
            await start_prescreening(message)
            return

        is_prescreening_complete = await pref_repo.is_prescreening_complete(account.id)
        if not is_prescreening_complete:
            # Existing user without completed prescreening
            await start_prescreening(message)
            return

    # User has completed prescreening - normal dialogue flow
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
