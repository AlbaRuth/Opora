"""Prescreening flow handlers."""

from __future__ import annotations

import time
from datetime import datetime
from dataclasses import dataclass, field

from aiogram import F, types

from core.config import get_settings
from core.intake_user_copy import build_intake_start_message, build_welcome_back_message
from core.logging import LogContexts, get_logger
from core.profile_labels import DEFAULT_THERAPIST_GENDER, DEFAULT_THERAPIST_NAME, THERAPIST_STYLES
from db.repositories import (
    AccountRepository,
    ClinicalProfileRepository,
    TherapistPreferenceRepository,
    UserProfileRepository,
)
from db.session import get_db_session
from integrations.telegram.bot import dispatcher
from integrations.telegram.prescreening_flow import (
    build_completion_profile_lines,
    migrate_traits_to_styles,
)
from integrations.telegram.prescreening_keyboards import (
    build_address_mode_keyboard,
    build_gender_keyboard,
    build_patient_sex_keyboard,
    build_skip_keyboard,
    build_styles_keyboard,
)
from integrations.telegram.prescreening_state import (
    PrescreeningWizardState,
    clear_wizard_state,
    get_wizard_state,
    is_in_prescreening as state_is_in_prescreening,
    save_wizard_state,
)
from services.dialogue_service import DialogueService
from services.prescreening_gate import evaluate_prescreening_gate

logger = get_logger(LogContexts.TELEGRAM)
LATENCY_BUDGET_MS = 500


@dataclass(slots=True)
class PrescreeningState:
    account_id: int = 0
    step: str = "awaiting_therapist_name"
    therapist_name: str = DEFAULT_THERAPIST_NAME
    therapist_gender: str = DEFAULT_THERAPIST_GENDER
    patient_name: str = ""
    patient_age: int | None = None
    patient_sex: str = "prefer_not_to_say"
    address_mode: str = "formal"
    selected_styles: list[str] = field(default_factory=list)
    is_edit_mode: bool = False
    processing_started_at: datetime | None = None


_compat_prescreening_states: dict[int, PrescreeningState] = {}


def get_prescreening_state(user_id: int) -> PrescreeningState | None:
    return _compat_prescreening_states.get(user_id)


def set_prescreening_state(user_id: int, state: PrescreeningState) -> None:
    _compat_prescreening_states[user_id] = state


async def start_prescreening(message: types.Message) -> None:
    """Start prescreening flow for user."""
    telegram_id = message.from_user.id
    logger.info("prescreening_started", user_id=telegram_id)

    async with get_db_session() as session:
        account_repo = AccountRepository(session)
        account = await account_repo.get_by_telegram_id(telegram_id)
        if not account:
            account = await account_repo.create_from_telegram(
                telegram_id=telegram_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )

    state = PrescreeningWizardState(account_id=account.id)
    await save_wizard_state(state)
    set_prescreening_state(telegram_id, PrescreeningState(account_id=account.id))

    await message.answer(
        "?? ????? ??????????! ??????? ???????? ?????? ?????????.\n\n"
        "<b>??? ?? ?????? ?? ??? ???????????</b>\n"
        f"(?? ?????????: {DEFAULT_THERAPIST_NAME})",
        reply_markup=build_skip_keyboard(),
    )


async def handle_prescreening_text(message: types.Message) -> bool:
    """Handle text input during prescreening."""
    user_id = message.from_user.id
    if not is_in_prescreening(user_id):
        return False

    text = message.text.strip() if message.text else ""
    if text.startswith("/"):
        return False

    compat_state = get_prescreening_state(user_id)
    if compat_state is not None:
        if compat_state.step == "awaiting_therapist_name":
            if text:
                compat_state.therapist_name = text[:50]
            compat_state.step = "awaiting_therapist_gender"
            await message.answer(
                "<b>???????? ??? ?????????:</b>\n(?? ?????????: ???????)",
                reply_markup=build_gender_keyboard(),
            )
            return True
        if compat_state.step == "awaiting_patient_name":
            if not text:
                await message.answer("Пожалуйста, введите имя или псевдоним.")
                return True
            compat_state.patient_name = text[:100]
            compat_state.step = "awaiting_patient_age"
            await message.answer("<b>??????? ??? ????</b>\n(??????? ?????, ????????: 25)")
            return True
        if compat_state.step == "awaiting_patient_age":
            try:
                age = int(text)
                if age < 13 or age > 120:
                    raise ValueError("Age out of range")
                compat_state.patient_age = age
                compat_state.step = "awaiting_patient_sex"
                await message.answer(
                    "<b>??? ???:</b>\n(??? ??????? ??? ????? ???????? ???)",
                    reply_markup=build_patient_sex_keyboard(),
                )
                return True
            except ValueError:
                await message.answer("Пожалуйста, введите корректный возраст.")
                return True

    state = await get_wizard_state(user_id)
    if not state:
        return False

    if state.step == "processing_completion":
        await message.answer("? ?????????, ???????? ????????? ???????")
        return True

    if state.step == "awaiting_therapist_name":
        if text:
            state.therapist_name = text[:50]
        await _ask_gender(message, state)
        return True

    if state.step == "awaiting_patient_name":
        if not text:
            await message.answer("Пожалуйста, введите имя или псевдоним.")
            return True
        state.patient_name = text[:100]
        state.step = "awaiting_patient_age"
        await save_wizard_state(state)
        await message.answer("<b>??????? ??? ????</b>\n(??????? ?????, ????????: 25)")
        return True

    if state.step == "awaiting_patient_age":
        try:
            age = int(text)
            if age < 13 or age > 120:
                raise ValueError("Age out of range")
            state.patient_age = age
            await _ask_patient_sex(message, state)
            return True
        except ValueError:
            await message.answer("Пожалуйста, введите корректный возраст.")
            return True

    return False


async def _ask_gender(message: types.Message, state: PrescreeningWizardState) -> None:
    state.step = "awaiting_therapist_gender"
    await save_wizard_state(state)
    await message.answer(
        "<b>???????? ??? ?????????:</b>\n(?? ?????????: ???????)",
        reply_markup=build_gender_keyboard(),
    )


async def _ask_patient_name(message: types.Message, state: PrescreeningWizardState) -> None:
    state.step = "awaiting_patient_name"
    await save_wizard_state(state)
    await message.answer("<b>??? ??? ? ??? ???????????</b>\n(??????? ???? ??? ??? ?????????)")


async def _ask_patient_sex(message: types.Message, state: PrescreeningWizardState) -> None:
    state.step = "awaiting_patient_sex"
    await save_wizard_state(state)
    await message.answer(
        "<b>??? ???:</b>\n(??? ??????? ??? ????? ???????? ???)",
        reply_markup=build_patient_sex_keyboard(),
    )


async def _ask_address_mode(message: types.Message, state: PrescreeningWizardState) -> None:
    state.step = "awaiting_address_mode"
    await save_wizard_state(state)
    await message.answer(
        "<b>??? ??? ? ??? ???????????</b>\n???????? ??????? ??? ??? ????? ???????:",
        reply_markup=build_address_mode_keyboard(),
    )


async def _ask_styles(message: types.Message, state: PrescreeningWizardState) -> None:
    state.step = "awaiting_styles_selection"
    await save_wizard_state(state)
    await message.answer(
        "<b>???????? ????? ??????? ?????????:</b>\n(????? ??????? ????????? ??? ????????????? ????????????)",
        reply_markup=build_styles_keyboard(state.selected_styles),
    )


async def _complete_prescreening(
    message: types.Message,
    state: PrescreeningWizardState,
    dialogue_service: DialogueService,
    user_id: int,
    original_start_time: float,
) -> None:
    step_start = time.time()
    logger.info(
        "prescreening_completing",
        user_id=user_id,
        therapist_name=state.therapist_name,
        therapist_gender=state.therapist_gender,
    )

    async with get_db_session() as session:
        account_repo = AccountRepository(session)
        account = await account_repo.get_by_telegram_id(user_id)
        if not account:
            logger.error("account_not_found_for_prescreening", telegram_id=user_id)
            await message.answer("?????? ?????????? ??????. ??????? /start")
            return

        therapist_repo = TherapistPreferenceRepository(session)
        await therapist_repo.update_preferences(
            account_id=account.id,
            therapist_name=state.therapist_name,
            therapist_gender=state.therapist_gender,
            therapist_styles=state.selected_styles,
            mark_complete=True,
        )

        user_profile_repo = UserProfileRepository(session)
        await user_profile_repo.update_profile(
            account_id=account.id,
            display_name=state.patient_name,
            age=state.patient_age,
            sex=state.patient_sex,
            address_mode=state.address_mode,
            mark_complete=True,
        )

        clinical_repo = ClinicalProfileRepository(session)
        card_filled = await clinical_repo.is_card_filled(account.id)
        patient_name = state.patient_name or ""

    db_duration_ms = int((time.time() - step_start) * 1000)
    if db_duration_ms > LATENCY_BUDGET_MS:
        logger.warning("prescreening_db_slow", user_id=user_id, duration_ms=db_duration_ms)

    await clear_wizard_state(user_id)
    clear_prescreening_state(user_id)

    profile_lines = build_completion_profile_lines(
        therapist_name=state.therapist_name,
        therapist_gender=state.therapist_gender,
        patient_name=state.patient_name,
        patient_age=state.patient_age,
        patient_sex=state.patient_sex,
        address_mode=state.address_mode,
        selected_styles=state.selected_styles,
    )
    await message.answer("\n".join(profile_lines))

    if card_filled:
        await message.answer(
            build_welcome_back_message(
                patient_name=patient_name,
                address_mode=state.address_mode,
                therapist_gender=state.therapist_gender,
            )
        )
    else:
        settings = get_settings()
        await message.answer(
            build_intake_start_message(
                patient_name=patient_name,
                address_mode=state.address_mode,
                therapist_gender=state.therapist_gender,
                min_user_turns=settings.intake_min_user_turns,
                max_user_turns=settings.intake_max_user_turns,
            )
        )

    try:
        await dialogue_service.create_session_silent(telegram_id=user_id)
    except Exception as exc:
        logger.error("auto_session_error", user_id=user_id, error=str(exc))

    total_duration_ms = int((time.time() - original_start_time) * 1000)
    logger.info("prescreening_completion_finished", user_id=user_id, total_duration_ms=total_duration_ms)


async def start_prescreening_for_edit(message: types.Message, user_id: int) -> None:
    """Start prescreening in edit mode using persisted state."""
    logger.info("prescreening_edit_started", user_id=user_id)
    async with get_db_session() as session:
        account_repo = AccountRepository(session)
        account = await account_repo.get_by_telegram_id(user_id)
        if not account:
            await message.answer("??????: ???????????? ?? ??????. ??????? /start")
            return

    state = PrescreeningWizardState(
        account_id=account.id,
        therapist_name=DEFAULT_THERAPIST_NAME,
        therapist_gender=DEFAULT_THERAPIST_GENDER,
        is_edit_mode=True,
    )

    if account.therapist_preference:
        pref = account.therapist_preference
        if pref.therapist_name:
            state.therapist_name = pref.therapist_name
        if pref.therapist_gender:
            state.therapist_gender = pref.therapist_gender
        if pref.therapist_traits:
            state.selected_styles = migrate_traits_to_styles(pref.therapist_traits)
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

    await save_wizard_state(state)
    set_prescreening_state(user_id, PrescreeningState(account_id=account.id, is_edit_mode=True))
    await message.answer(
        "?? <b>?????????????? ??????</b>\n\n"
        "??????? ??????? ????????? ?????? ?????????.\n\n"
        "<b>??? ?? ?????? ?? ??? ???????????</b>\n"
        f"(???????: {state.therapist_name})",
        reply_markup=build_skip_keyboard(),
    )


@dispatcher.callback_query(F.data == "prescreen:skip_name")
async def on_skip_name(callback: types.CallbackQuery) -> None:
    await callback.answer("?????????")
    state = await get_wizard_state(callback.from_user.id)
    if not state or state.step != "awaiting_therapist_name":
        return
    await _ask_gender(callback.message, state)


@dispatcher.callback_query(F.data.startswith("prescreen:gender:"))
async def on_gender_select(callback: types.CallbackQuery) -> None:
    state = await get_wizard_state(callback.from_user.id)
    if not state or state.step != "awaiting_therapist_gender":
        await callback.answer("?????????? ??????")
        return
    gender = callback.data.split(":")[-1]
    state.therapist_gender = gender
    await save_wizard_state(state)
    label = "???????" if gender == "female" else "???????"
    await callback.answer(f"??????: {label}")
    await callback.message.edit_text(f"<b>?????? ??? ?????????:</b> {label}")
    await _ask_patient_name(callback.message, state)


@dispatcher.callback_query(F.data.startswith("prescreen:sex:"))
async def on_patient_sex_select(callback: types.CallbackQuery) -> None:
    state = await get_wizard_state(callback.from_user.id)
    if not state or state.step != "awaiting_patient_sex":
        await callback.answer("?????????? ??????")
        return
    sex = callback.data.split(":")[-1]
    state.patient_sex = sex
    await save_wizard_state(state)
    label = "???????" if sex == "male" else ("???????" if sex == "female" else "?? ??????")
    await callback.answer(f"??????: {label}")
    await callback.message.edit_text(f"<b>??? ???:</b> {label}")
    await _ask_address_mode(callback.message, state)


@dispatcher.callback_query(F.data.startswith("prescreen:address:"))
async def on_address_mode_select(callback: types.CallbackQuery) -> None:
    state = await get_wizard_state(callback.from_user.id)
    if not state or state.step != "awaiting_address_mode":
        await callback.answer("?????????? ??????")
        return
    address_mode = callback.data.split(":")[-1]
    state.address_mode = address_mode
    await save_wizard_state(state)
    label = "?? '??'" if address_mode == "informal" else "?? '??'"
    await callback.answer(f"???????: {label}")
    await callback.message.edit_text(f"<b>????? ?????????:</b> {label}")
    await _ask_styles(callback.message, state)


@dispatcher.callback_query(F.data.startswith("prescreen:style:"))
async def on_style_toggle(callback: types.CallbackQuery) -> None:
    state = await get_wizard_state(callback.from_user.id)
    if not state or state.step != "awaiting_styles_selection":
        await callback.answer("?????????? ??????")
        return
    style_id = callback.data.split(":")[-1]
    if style_id in state.selected_styles:
        state.selected_styles.remove(style_id)
    else:
        state.selected_styles.append(style_id)
    await save_wizard_state(state)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=build_styles_keyboard(state.selected_styles))


@dispatcher.callback_query(F.data == "prescreen:styles_done")
async def on_styles_done(callback: types.CallbackQuery, dialogue_service: DialogueService) -> None:
    state = await get_wizard_state(callback.from_user.id)
    if not state or state.step != "awaiting_styles_selection":
        await callback.answer("?????????? ??????")
        return
    if not state.selected_styles:
        await callback.answer("???????? ???? ?? ???? ?????")
        return

    state.step = "processing_completion"
    state.processing_started_at = datetime.utcnow()
    await save_wizard_state(state)
    await callback.answer("??????!")
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _complete_prescreening(
        message=callback.message,
        state=state,
        dialogue_service=dialogue_service,
        user_id=callback.from_user.id,
        original_start_time=time.time(),
    )


async def check_and_handle_prescreening(message: types.Message) -> bool:
    """Return True when prescreening started or continued."""
    user_id = message.from_user.id
    try:
        async with get_db_session() as session:
            gate = await evaluate_prescreening_gate(user_id, session)
        if gate.account_exists and gate.is_complete:
            clear_prescreening_state(user_id)
            return False
        await start_prescreening(message)
        return True
    except Exception:
        if is_in_prescreening(user_id):
            return await handle_prescreening_text(message)
        return False


def clear_prescreening_state(user_id: int) -> None:
    _compat_prescreening_states.pop(user_id, None)


def is_in_prescreening(user_id: int) -> bool:
    return user_id in _compat_prescreening_states
