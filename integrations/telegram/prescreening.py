"""
Prescreening flow for new users.
Multi-step wizard with inline keyboards for therapist personalization.
NEW: Includes patient sex (male/female/prefer_not_to_say) and address mode (ты/вы).
"""

import time
from dataclasses import dataclass, field
from typing import ClassVar

from aiogram import F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.config import get_settings
from core.intake_user_copy import build_intake_start_message
from core.logging import get_logger, LogContexts
from db.session import get_db_session
from db.repositories import (
    AccountRepository,
    TherapistPreferenceRepository,
    UserProfileRepository,
)

# Import shared dispatcher from bot to avoid creating separate instance
from integrations.telegram.bot import dispatcher

# Type hint import for dialogue service
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from services.dialogue_service import DialogueService

logger = get_logger(LogContexts.TELEGRAM)

# Latency budget threshold in seconds for non-LLM operations
LATENCY_BUDGET_MS = 500

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
    # NEW: Patient sex (male/female/prefer_not_to_say)
    patient_sex: str = "prefer_not_to_say"
    # NEW: Address mode (formal=вы, informal=ты)
    address_mode: str = "formal"
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
    """Build keyboard for therapist gender selection."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Мужской", callback_data="prescreen:gender:male"),
        InlineKeyboardButton(text="Женский", callback_data="prescreen:gender:female"),
    )
    return builder.as_markup()


def build_patient_sex_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for patient sex selection."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Мужской", callback_data="prescreen:sex:male"),
        InlineKeyboardButton(text="Женский", callback_data="prescreen:sex:female"),
    )
    builder.row(
        InlineKeyboardButton(text="Не хочу указывать", callback_data="prescreen:sex:prefer_not_to_say"),
    )
    return builder.as_markup()


def build_address_mode_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for address mode selection (ты/вы)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text='На «Вы»', callback_data="prescreen:address:formal"),
        InlineKeyboardButton(text='На «Ты»', callback_data="prescreen:address:informal"),
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

    # Ensure user exists in database using new repositories
    async with get_db_session() as session:
        account_repo = AccountRepository(session)
        account = await account_repo.get_by_telegram_id(user_id)
        if not account:
            account = await account_repo.create_from_telegram(
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
    Commands (text starting with /) are ignored and not processed as answers.
    """
    user_id = message.from_user.id

    if not is_in_prescreening(user_id):
        return False

    state = get_prescreening_state(user_id)
    if not state:
        return False

    # Guard: don't process commands as prescreening answers
    text = message.text.strip() if message.text else ""
    if text.startswith("/"):
        logger.debug("command_ignored_in_prescreening", user_id=user_id, command=text[:20])
        return False  # Let command handlers process it

    # Guard: don't process if in completion phase
    if state.step == "processing_completion":
        logger.debug("prescreening_completion_in_progress", user_id=user_id)
        await message.answer("⏳ Подождите, завершаю настройку профиля...")
        return True

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
            # NEW: After age, ask for sex
            state.step = "awaiting_patient_sex"
            await _ask_patient_sex(message, state)
            return True
        except ValueError:
            await message.answer(
                "⚠️ Пожалуйста, введите корректный возраст"
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


async def _ask_patient_sex(message: types.Message, state: PrescreeningState) -> None:
    """NEW: Ask for patient sex."""
    state.step = "awaiting_patient_sex"
    await message.answer(
        "<b>Ваш пол:</b>\n"
        "(это поможет мне лучше понимать вас)",
        reply_markup=build_patient_sex_keyboard(),
    )


async def _ask_address_mode(message: types.Message, state: PrescreeningState) -> None:
    """NEW: Ask for address mode (ты/вы)."""
    state.step = "awaiting_address_mode"
    await message.answer(
        "<b>Как мне к вам обращаться?</b>\n"
        "Выберите удобный для вас стиль общения:",
        reply_markup=build_address_mode_keyboard(),
    )


async def _ask_traits(message: types.Message, state: PrescreeningState) -> None:
    """Ask for therapist traits selection."""
    await message.answer(
        "<b>Выберите черты характера психолога:</b>\n"
        "(можно выбрать несколько, минимум 1)",
        reply_markup=build_traits_keyboard(state.selected_traits),
    )


def _get_trait_labels(trait_ids: list[str]) -> list[str]:
    """Convert trait IDs to Russian labels."""
    trait_map = dict(THERAPIST_TRAITS)
    return [trait_map.get(tid, tid) for tid in trait_ids]


def _get_sex_label(sex: str) -> str:
    """Convert sex ID to Russian label."""
    mapping = {
        "male": "Мужской",
        "female": "Женский",
        "prefer_not_to_say": "Не указан",
    }
    return mapping.get(sex, "Не указан")


def _get_address_mode_label(mode: str) -> str:
    """Convert address mode ID to Russian label."""
    mapping = {
        "formal": "На 'Вы'",
        "informal": "На 'Ты'",
    }
    return mapping.get(mode, "На 'Вы'")


async def _complete_prescreening(
    message: types.Message,
    state: PrescreeningState,
    user_id: int | None = None,
    original_start_time: float | None = None,
) -> None:
    """Save prescreening data and complete with auto-next message."""
    step_start = time.time()
    actual_user_id = user_id if user_id is not None else message.from_user.id

    logger.info(
        "prescreening_completing",
        user_id=actual_user_id,
        therapist_name=state.therapist_name,
        therapist_gender=state.therapist_gender,
        patient_sex=state.patient_sex,
        address_mode=state.address_mode,
        traits_count=len(state.selected_traits),
    )

    # Save to database using new repositories
    async with get_db_session() as session:
        account_repo = AccountRepository(session)
        account = await account_repo.get_by_telegram_id(actual_user_id)

        if account:
            # Update therapist preferences
            therapist_repo = TherapistPreferenceRepository(session)
            await therapist_repo.update_preferences(
                account_id=account.id,
                therapist_name=state.therapist_name,
                therapist_gender=state.therapist_gender,
                therapist_traits=state.selected_traits,
                mark_complete=True,
            )

            # Update user profile (NEW: includes sex and address_mode)
            user_profile_repo = UserProfileRepository(session)
            await user_profile_repo.update_profile(
                account_id=account.id,
                display_name=state.patient_name,
                age=state.patient_age,
                sex=state.patient_sex,
                address_mode=state.address_mode,
                mark_complete=True,
            )

            # Check if clinical card is filled
            from db.repositories import ClinicalProfileRepository
            clinical_repo = ClinicalProfileRepository(session)
            card_filled = await clinical_repo.is_card_filled(account.id)
            db_account_id = account.id
            patient_name = state.patient_name or ""
        else:
            logger.error("account_not_found_for_prescreening", telegram_id=actual_user_id)
            card_filled = False
            db_account_id = None
            patient_name = ""

    db_duration_ms = int((time.time() - step_start) * 1000)
    logger.info("prescreening_db_saved", user_id=actual_user_id, account_id=db_account_id, db_duration_ms=db_duration_ms)

    # Check latency budget
    if db_duration_ms > LATENCY_BUDGET_MS:
        logger.warning("prescreening_db_slow", user_id=actual_user_id, duration_ms=db_duration_ms, budget_ms=LATENCY_BUDGET_MS)

    # Clear state
    clear_prescreening_state(actual_user_id)

    # Confirm completion with updated emoji - NEW fields included
    gender_label = "Женский" if state.therapist_gender == "female" else "Мужской"
    sex_label = _get_sex_label(state.patient_sex)
    address_label = _get_address_mode_label(state.address_mode)
    traits_labels = _get_trait_labels(state.selected_traits)

    # Build profile summary
    profile_lines = [
        "✅ <b>Профиль обновлен!</b>",
        "",
        f"🧠 Имя психолога: {state.therapist_name}",
        f"⚧ Пол психолога: {gender_label}",
        "",
        f"👤 Ваше имя: {state.patient_name}",
        f"🎂 Возраст: {state.patient_age}",
        f"⚥ Ваш пол: {sex_label}",
        f"💬 Обращение: {address_label}",
        f"✨ Характер: {', '.join(traits_labels)}",
    ]

    await message.answer("\n".join(profile_lines))

    profile_duration_ms = int((time.time() - step_start) * 1000)

    # Auto-send next message based on card status
    next_msg_start = time.time()
    if card_filled:
        # Card already has data - welcome back message
        welcome_msg = _build_welcome_back_message(
            patient_name, state.address_mode, state.therapist_gender
        )
        await message.answer(welcome_msg)
        logger.info("auto_sent_welcome_back", user_id=actual_user_id, card_filled=True)
    else:
        # Card empty - intake script message (rounds from INTAKE_* .env)
        settings = get_settings()
        intake_msg = build_intake_start_message(
            patient_name,
            state.address_mode,
            state.therapist_gender,
            settings.intake_min_user_turns,
            settings.intake_max_user_turns,
        )
        await message.answer(intake_msg)
        logger.info("auto_sent_intake_script", user_id=actual_user_id, card_filled=False)

    next_msg_duration_ms = int((time.time() - next_msg_start) * 1000)

    # Auto-create session so user can start messaging immediately
    session_start = time.time()
    try:
        # Get dialogue_service from dispatcher context
        from typing import cast
        from services.dialogue_service import DialogueService
        dialogue_service = cast(DialogueService | None, dispatcher.get("dialogue_service"))
        if dialogue_service:
            session_created = await dialogue_service.create_session_silent(
                telegram_id=actual_user_id
            )
            if session_created:
                logger.info("auto_session_created", user_id=actual_user_id, after_prescreening=True)
            else:
                logger.warning("auto_session_failed", user_id=actual_user_id)
        else:
            logger.warning("dialogue_service_not_available", user_id=actual_user_id)
    except Exception as e:
        logger.error("auto_session_error", user_id=actual_user_id, error=str(e))

    session_duration_ms = int((time.time() - session_start) * 1000)
    total_duration_ms = int((time.time() - (original_start_time or step_start)) * 1000)

    logger.info(
        "prescreening_completion_finished",
        user_id=actual_user_id,
        db_duration_ms=db_duration_ms,
        profile_duration_ms=profile_duration_ms,
        next_msg_duration_ms=next_msg_duration_ms,
        session_duration_ms=session_duration_ms,
        total_duration_ms=total_duration_ms,
    )

    if total_duration_ms > LATENCY_BUDGET_MS:
        logger.warning("prescreening_total_slow", user_id=actual_user_id, duration_ms=total_duration_ms, budget_ms=LATENCY_BUDGET_MS)


def _build_welcome_back_message(
    patient_name: str,
    address_mode: str = "formal",
    therapist_gender: str = "female",
) -> str:
    """Build welcome back message when card IS already filled."""
    name = patient_name or "друг"
    tg = therapist_gender if therapist_gender in ("female", "male") else "female"
    glad = "Рада" if tg == "female" else "Рад"

    # Adjust greeting based on address mode
    if address_mode == "informal":
        # Informal (ты)
        return (
            f"Привет, {name}! {glad} тебя видеть. "
            "Расскажи, как прошел твой день?"
        )
    else:
        # Formal (вы) - default
        return (
            f"Привет, {name}! {glad} вас видеть. "
            "Расскажите, как прошел ваш день?"
        )


async def start_prescreening_for_edit(message: types.Message, user_id: int) -> None:
    """Start prescreening flow for editing existing profile."""
    logger.info("prescreening_edit_started", user_id=user_id)

    # Load current user data to pre-fill using new repositories
    async with get_db_session() as session:
        account_repo = AccountRepository(session)
        account = await account_repo.get_by_telegram_id(user_id)

        if not account:
            logger.error("account_not_found_for_edit", telegram_id=user_id)
            await message.answer("Ошибка: пользователь не найден. Нажмите /start")
            return

    # Initialize state with edit mode flag
    state = PrescreeningState()
    state._is_edit_mode = True  # Mark as edit mode

    # Pre-fill with existing values if available
    if account.therapist_preference:
        pref = account.therapist_preference
        if pref.therapist_name:
            state.therapist_name = pref.therapist_name
        if pref.therapist_gender:
            state.therapist_gender = pref.therapist_gender
        if pref.therapist_traits:
            state.selected_traits = list(pref.therapist_traits)

    # NEW: Pre-fill user profile data
    if account.user_profile:
        profile = account.user_profile
        if profile.display_name:
            state.patient_name = profile.display_name
        if profile.age:
            state.patient_age = profile.age
        if profile.sex:
            state.patient_sex = profile.sex
        if profile.address_mode:
            state.address_mode = profile.address_mode

    set_prescreening_state(user_id, state)

    await message.answer(
        "📝 <b>Редактирование анкеты</b>\n\n"
        "Давайте обновим настройки вашего психолога.\n\n"
        "<b>Как вы хотите ко мне обращаться?</b>\n"
        f"(текущее: {state.therapist_name})",
        reply_markup=build_skip_keyboard(),
    )


# Callback handlers
@dispatcher.callback_query(F.data == "prescreen:skip_name")
async def on_skip_name(callback: types.CallbackQuery) -> None:
    """Handle Skip button for therapist name."""
    start_time = time.time()
    user_id = callback.from_user.id

    # Fast response to prevent Telegram loading indicator
    await callback.answer("Пропущено")

    state = get_prescreening_state(user_id)
    if not state or state.step != "awaiting_therapist_name":
        logger.debug("skip_name_outdated", user_id=user_id, step=getattr(state, 'step', None))
        return

    await _ask_gender(callback.message, state)
    logger.debug("skip_name_processed", user_id=user_id, duration_ms=int((time.time() - start_time) * 1000))


@dispatcher.callback_query(F.data.startswith("prescreen:gender:"))
async def on_gender_select(callback: types.CallbackQuery) -> None:
    """Handle therapist gender selection."""
    start_time = time.time()
    user_id = callback.from_user.id

    state = get_prescreening_state(user_id)
    if not state or state.step != "awaiting_therapist_gender":
        await callback.answer("Устаревшая кнопка")
        logger.debug("gender_select_outdated", user_id=user_id, step=getattr(state, 'step', None))
        return

    gender = callback.data.split(":")[-1]
    state.therapist_gender = gender

    gender_label = "Женский" if gender == "female" else "Мужской"

    # Fast operations parallel where possible
    try:
        # Answer callback first
        await callback.answer(f"Выбран: {gender_label}")

        # Edit message to show selection
        await callback.message.edit_text(
            f"<b>Выбран пол психолога:</b> {gender_label}"
        )

        # Continue flow
        await _ask_patient_name(callback.message, state)
    except Exception as e:
        logger.warning("gender_select_error", user_id=user_id, error=str(e))

    logger.debug("gender_select_processed", user_id=user_id, gender=gender, duration_ms=int((time.time() - start_time) * 1000))


# NEW: Patient sex selection handler
@dispatcher.callback_query(F.data.startswith("prescreen:sex:"))
async def on_patient_sex_select(callback: types.CallbackQuery) -> None:
    """Handle patient sex selection."""
    start_time = time.time()
    user_id = callback.from_user.id

    state = get_prescreening_state(user_id)
    if not state or state.step != "awaiting_patient_sex":
        await callback.answer("Устаревшая кнопка")
        logger.debug("sex_select_outdated", user_id=user_id, step=getattr(state, 'step', None))
        return

    sex = callback.data.split(":")[-1]
    state.patient_sex = sex

    sex_label = _get_sex_label(sex)

    try:
        # Answer callback first
        await callback.answer(f"Выбран: {sex_label}")

        # Edit message to show selection
        await callback.message.edit_text(
            f"<b>Ваш пол:</b> {sex_label}"
        )

        # Continue to address mode selection (NEW)
        await _ask_address_mode(callback.message, state)
    except Exception as e:
        logger.warning("sex_select_error", user_id=user_id, error=str(e))

    logger.debug("sex_select_processed", user_id=user_id, sex=sex, duration_ms=int((time.time() - start_time) * 1000))


# NEW: Address mode selection handler
@dispatcher.callback_query(F.data.startswith("prescreen:address:"))
async def on_address_mode_select(callback: types.CallbackQuery) -> None:
    """Handle address mode selection (ты/вы)."""
    start_time = time.time()
    user_id = callback.from_user.id

    state = get_prescreening_state(user_id)
    if not state or state.step != "awaiting_address_mode":
        await callback.answer("Устаревшая кнопка")
        logger.debug("address_select_outdated", user_id=user_id, step=getattr(state, 'step', None))
        return

    address_mode = callback.data.split(":")[-1]
    state.address_mode = address_mode

    address_label = _get_address_mode_label(address_mode)

    try:
        # Answer callback first
        await callback.answer(f"Выбрано: {address_label}")

        # Edit message to show selection
        await callback.message.edit_text(
            f"<b>Стиль обращения:</b> {address_label}"
        )

        # Continue to traits selection
        state.step = "awaiting_traits_selection"
        await _ask_traits(callback.message, state)
    except Exception as e:
        logger.warning("address_select_error", user_id=user_id, error=str(e))

    logger.debug("address_select_processed", user_id=user_id, mode=address_mode, duration_ms=int((time.time() - start_time) * 1000))


@dispatcher.callback_query(F.data.startswith("prescreen:trait:"))
async def on_trait_toggle(callback: types.CallbackQuery) -> None:
    """Handle trait toggle in multi-selection."""
    start_time = time.time()
    user_id = callback.from_user.id

    state = get_prescreening_state(user_id)
    if not state or state.step != "awaiting_traits_selection":
        await callback.answer("Устаревшая кнопка")
        logger.debug("trait_toggle_outdated", user_id=user_id, step=getattr(state, 'step', None))
        return

    trait_id = callback.data.split(":")[-1]

    # Toggle selection
    if trait_id in state.selected_traits:
        state.selected_traits.remove(trait_id)
        action = "removed"
    else:
        state.selected_traits.append(trait_id)
        action = "added"

    # Fast response and keyboard update
    try:
        await callback.answer()  # Empty answer is fast
        await callback.message.edit_reply_markup(
            reply_markup=build_traits_keyboard(state.selected_traits)
        )
    except Exception as e:
        logger.warning("trait_toggle_error", user_id=user_id, trait=trait_id, error=str(e))

    duration_ms = int((time.time() - start_time) * 1000)
    if duration_ms > 200:  # Trait toggle should be very fast
        logger.warning("trait_toggle_slow", user_id=user_id, trait=trait_id, action=action, duration_ms=duration_ms)
    else:
        logger.debug("trait_toggle_processed", user_id=user_id, trait=trait_id, action=action, duration_ms=duration_ms)


@dispatcher.callback_query(F.data == "prescreen:traits_done")
async def on_traits_done(callback: types.CallbackQuery) -> None:
    """Handle completion of traits selection with performance tracking."""
    start_time = time.time()
    user_id = callback.from_user.id
    state = get_prescreening_state(user_id)

    if not state or state.step != "awaiting_traits_selection":
        await callback.answer("Устаревшая кнопка")
        return

    if not state.selected_traits:
        await callback.answer("Выберите хотя бы одну черту")
        return

    # Mark as processing to prevent double-clicks and concurrent processing
    state.step = "processing_completion"
    state._processing_start_time = start_time

    await callback.answer("Готово!")

    # Try to delete the traits selection message for cleaner UX
    try:
        await callback.message.delete()
        logger.debug("traits_message_deleted", user_id=user_id, latency_ms=int((time.time() - start_time) * 1000))
    except Exception as e:
        # Fallback: edit text to show completion
        logger.debug("traits_message_delete_failed", user_id=user_id, error=str(e))
        try:
            await callback.message.edit_text("✅ Выбор завершен")
        except Exception:
            pass

    step1_time = time.time()
    await _complete_prescreening(callback.message, state, user_id=user_id, original_start_time=start_time)

    total_duration_ms = int((time.time() - start_time) * 1000)
    logger.info("prescreening_completion_finished", user_id=user_id, total_duration_ms=total_duration_ms)


async def check_and_handle_prescreening(message: types.Message) -> bool:
    """
    Check if user needs prescreening and handle it.
    Returns True if prescreening was initiated or handled, False otherwise.
    """
    user_id = message.from_user.id

    # If already in prescreening, continue it
    if is_in_prescreening(user_id):
        return await handle_prescreening_text(message)

    # Check if user exists and has completed prescreening using new repositories
    async with get_db_session() as session:
        account_repo = AccountRepository(session)
        account = await account_repo.get_by_telegram_id(user_id)

        if not account:
            # New user - start prescreening
            await start_prescreening(message)
            return True

        # Check prescreening completion via therapist_preference
        pref_repo = TherapistPreferenceRepository(session)
        is_complete = await pref_repo.is_prescreening_complete(account.id)

        if not is_complete:
            # Existing user without completed prescreening
            await start_prescreening(message)
            return True

    return False
