"""
Prescreening flow for new users.
Multi-step wizard with inline keyboards for therapist personalization.
"""

from dataclasses import dataclass, field
from typing import ClassVar

from aiogram import F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.logging import get_logger, LogContexts
from db.session import get_db_session
from db.repositories import UserRepository

# Import shared dispatcher from bot to avoid creating separate instance
from integrations.telegram.bot import dispatcher

logger = get_logger(LogContexts.TELEGRAM)

# Available therapist traits
THERAPIST_TRAITS = [
    ("strict", "Строгий"),
    ("business", "Деловой"),
    ("calm", "Спокойный"),
    ("kind", "Добрый"),
    ("restrained", "Сдержанный"),
    ("empathetic", "Эмпатичный"),
]

DEFAULT_THERAPIST_NAME = "Опора"
DEFAULT_THERAPIST_GENDER = "female"


@dataclass
class PrescreeningState:
    """Temporary state for prescreening flow."""
    
    step: str = "awaiting_therapist_name"
    therapist_name: str = DEFAULT_THERAPIST_NAME
    therapist_gender: str = DEFAULT_THERAPIST_GENDER
    patient_name: str = ""
    patient_age: int | None = None
    selected_traits: list[str] = field(default_factory=list)


# In-memory storage for prescreening states (user_id -> state)
# In production, consider using Redis or database
_prescreening_states: dict[int, PrescreeningState] = {}


def get_prescreening_state(user_id: int) -> PrescreeningState | None:
    """Get current prescreening state for user."""
    return _prescreening_states.get(user_id)


def set_prescreening_state(user_id: int, state: PrescreeningState) -> None:
    """Set prescreening state for user."""
    _prescreening_states[user_id] = state


def clear_prescreening_state(user_id: int) -> None:
    """Clear prescreening state for user."""
    _prescreening_states.pop(user_id, None)


def is_in_prescreening(user_id: int) -> bool:
    """Check if user is currently in prescreening flow."""
    return user_id in _prescreening_states


def build_skip_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard with Skip button."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Пропустить", callback_data="prescreen:skip_name"))
    return builder.as_markup()


def build_gender_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for gender selection."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Мужской", callback_data="prescreen:gender:male"),
        InlineKeyboardButton(text="Женский", callback_data="prescreen:gender:female"),
    )
    return builder.as_markup()


def build_traits_keyboard(selected_traits: list[str]) -> InlineKeyboardMarkup:
    """Build keyboard for traits multi-selection."""
    builder = InlineKeyboardBuilder()
    
    for trait_id, trait_label in THERAPIST_TRAITS:
        is_selected = trait_id in selected_traits
        prefix = "✅ " if is_selected else "⬜ "
        builder.row(
            InlineKeyboardButton(
                text=f"{prefix}{trait_label}",
                callback_data=f"prescreen:trait:{trait_id}"
            )
        )
    
    # Add Done button if at least one trait selected
    if selected_traits:
        builder.row(
            InlineKeyboardButton(text="✓ Готово", callback_data="prescreen:traits_done")
        )
    
    return builder.as_markup()


async def start_prescreening(message: types.Message) -> None:
    """Start prescreening flow for user."""
    user_id = message.from_user.id

    logger.info("prescreening_started", user_id=user_id)

    # Ensure user exists in database
    async with get_db_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_id)
        if not user:
            user = await user_repo.create_from_telegram(
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
    
    # Initialize state
    state = PrescreeningState()
    set_prescreening_state(user_id, state)
    
    await message.answer(
        "👋 Добро пожаловать! Давайте настроим вашего психолога.\n\n"
        "<b>Как вы хотите ко мне обращаться?</b>\n"
        f"(по умолчанию: {DEFAULT_THERAPIST_NAME})",
        reply_markup=build_skip_keyboard(),
    )


async def handle_prescreening_text(message: types.Message) -> bool:
    """
    Handle text input during prescreening.
    Returns True if message was handled, False otherwise.
    """
    user_id = message.from_user.id
    
    if not is_in_prescreening(user_id):
        return False
    
    state = get_prescreening_state(user_id)
    if not state:
        return False
    
    text = message.text.strip() if message.text else ""
    
    if state.step == "awaiting_therapist_name":
        # User provided custom therapist name
        if text:
            state.therapist_name = text[:50]  # Limit length
        await _ask_gender(message, state)
        return True
    
    elif state.step == "awaiting_patient_name":
        # User provided their name/pseudonym
        if not text:
            await message.answer(
                "⚠️ Пожалуйста, введите ваше имя или псевдоним."
            )
            return True
        state.patient_name = text[:100]
        state.step = "awaiting_patient_age"
        await message.answer(
            "<b>Сколько вам лет?</b>\n"
            "(укажите число, например: 25)"
        )
        return True
    
    elif state.step == "awaiting_patient_age":
        # User provided age - validate
        try:
            age = int(text)
            if age < 13 or age > 120:
                raise ValueError("Age out of range")
            state.patient_age = age
            state.step = "awaiting_traits_selection"
            await _ask_traits(message, state)
            return True
        except ValueError:
            await message.answer(
                "⚠️ Пожалуйста, введите корректный возраст (число от 13 до 120)."
            )
            return True
    
    return False


async def _ask_gender(message: types.Message, state: PrescreeningState) -> None:
    """Ask for therapist gender."""
    state.step = "awaiting_therapist_gender"
    await message.answer(
        "<b>Выберите пол психолога:</b>\n"
        "(по умолчанию: Женский)",
        reply_markup=build_gender_keyboard(),
    )


async def _ask_patient_name(message: types.Message, state: PrescreeningState) -> None:
    """Ask for patient name/pseudonym."""
    state.step = "awaiting_patient_name"
    await message.answer(
        "<b>Как мне к вам обращаться?</b>\n"
        "(введите ваше имя или псевдоним)"
    )


async def _ask_traits(message: types.Message, state: PrescreeningState) -> None:
    """Ask for therapist traits selection."""
    await message.answer(
        "<b>Выберите черты характера психолога:</b>\n"
        "(можно выбрать несколько, минимум 1)",
        reply_markup=build_traits_keyboard(state.selected_traits),
    )


async def _complete_prescreening(
    message: types.Message,
    state: PrescreeningState,
    user_id: int | None = None
) -> None:
    """Save prescreening data and complete."""
    # Use provided user_id or fall back to message (for backwards compatibility)
    actual_user_id = user_id if user_id is not None else message.from_user.id

    logger.info(
        "prescreening_completing",
        user_id=actual_user_id,
        therapist_name=state.therapist_name,
        therapist_gender=state.therapist_gender,
        traits_count=len(state.selected_traits),
    )
    
    # Save to database
    async with get_db_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(actual_user_id)

        if user:
            await user_repo.update_prescreening_profile(
                user_id=user.id,
                therapist_name=state.therapist_name,
                therapist_gender=state.therapist_gender,
                patient_display_name=state.patient_name,
                patient_age=state.patient_age,
                therapist_traits=state.selected_traits,
                mark_complete=True,
            )
            logger.info("prescreening_saved", user_id=actual_user_id, db_user_id=user.id)
        else:
            logger.error("user_not_found_for_prescreening", telegram_id=actual_user_id)

    # Clear state
    clear_prescreening_state(actual_user_id)
    
    # Confirm completion
    gender_label = "Женский" if state.therapist_gender == "female" else "Мужской"
    traits_labels = [
        label for tid, label in THERAPIST_TRAITS 
        if tid in state.selected_traits
    ]
    
    await message.answer(
        f"✅ <b>Профиль настроен!</b>\n\n"
        f"🤖 Имя психолога: {state.therapist_name}\n"
        f"⚧ Пол: {gender_label}\n"
        f"👤 Ваше имя: {state.patient_name}\n"
        f"🎂 Возраст: {state.patient_age}\n"
        f"✨ Характер: {', '.join(traits_labels)}\n\n"
        f"Начинаем сессию..."
    )


# Callback handlers
@dispatcher.callback_query(F.data == "prescreen:skip_name")
async def on_skip_name(callback: types.CallbackQuery) -> None:
    """Handle Skip button for therapist name."""
    user_id = callback.from_user.id
    state = get_prescreening_state(user_id)

    if not state or state.step != "awaiting_therapist_name":
        await callback.answer("Устаревшая кнопка")
        return

    await callback.answer("Пропущено")
    await _ask_gender(callback.message, state)


@dispatcher.callback_query(F.data.startswith("prescreen:gender:"))
async def on_gender_select(callback: types.CallbackQuery) -> None:
    """Handle gender selection."""
    user_id = callback.from_user.id
    state = get_prescreening_state(user_id)
    
    if not state or state.step != "awaiting_therapist_gender":
        await callback.answer("Устаревшая кнопка")
        return
    
    gender = callback.data.split(":")[-1]
    state.therapist_gender = gender
    
    gender_label = "Женский" if gender == "female" else "Мужской"
    await callback.answer(f"Выбран: {gender_label}")
    
    # Edit message to show selection
    await callback.message.edit_text(
        f"<b>Выбран пол психолога:</b> {gender_label}"
    )
    
    await _ask_patient_name(callback.message, state)


@dispatcher.callback_query(F.data.startswith("prescreen:trait:"))
async def on_trait_toggle(callback: types.CallbackQuery) -> None:
    """Handle trait toggle in multi-selection."""
    user_id = callback.from_user.id
    state = get_prescreening_state(user_id)
    
    if not state or state.step != "awaiting_traits_selection":
        await callback.answer("Устаревшая кнопка")
        return
    
    trait_id = callback.data.split(":")[-1]
    
    # Toggle selection
    if trait_id in state.selected_traits:
        state.selected_traits.remove(trait_id)
    else:
        state.selected_traits.append(trait_id)
    
    await callback.answer()
    
    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=build_traits_keyboard(state.selected_traits)
    )


@dispatcher.callback_query(F.data == "prescreen:traits_done")
async def on_traits_done(callback: types.CallbackQuery) -> None:
    """Handle completion of traits selection."""
    user_id = callback.from_user.id
    state = get_prescreening_state(user_id)

    if not state or state.step != "awaiting_traits_selection":
        await callback.answer("Устаревшая кнопка")
        return

    if not state.selected_traits:
        await callback.answer("Выберите хотя бы одну черту")
        return

    # Mark as processing to prevent double-clicks
    state.step = "processing_completion"

    await callback.answer("Готово!")
    await _complete_prescreening(callback.message, state, user_id=user_id)


async def check_and_handle_prescreening(message: types.Message) -> bool:
    """
    Check if user needs prescreening and handle it.
    Returns True if prescreening was initiated or handled, False otherwise.
    """
    user_id = message.from_user.id
    
    # If already in prescreening, continue it
    if is_in_prescreening(user_id):
        return await handle_prescreening_text(message)
    
    # Check if user exists and has completed prescreening
    async with get_db_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_id)
        
        if not user:
            # New user - start prescreening
            await start_prescreening(message)
            return True
        
        if not user.is_prescreening_complete:
            # Existing user without completed prescreening
            await start_prescreening(message)
            return True
    
    return False
