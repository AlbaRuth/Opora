"""
Dialogue service - main orchestrator for user interactions.
Coordinates between Telegram, Agents, and Database.
NEW: Uses normalized schema (identity/profile/clinical/therapy/observability).
"""

from typing import Any

from agents.core import IntakeAgent, SessionState, TherapistAgent
from core.config import get_settings
from core.logging import get_logger, LogContexts
from db.repositories import (
    AccountRepository,
    ClinicalProfileRepository,
    IntakeStateRepository,
    MessageRepository,
    SessionRepository,
    TherapistPreferenceRepository,
    UserProfileRepository,
)
from db.session import get_db_session
from integrations.langfuse import LangfuseClient, trace_scope

logger = get_logger(LogContexts.SERVICE)


class DialogueService:
    """Service for managing dialogue sessions."""

    def __init__(
        self,
        therapist_agent: TherapistAgent | None = None,
        intake_agent: IntakeAgent | None = None,
    ):
        self.settings = get_settings()
        self.therapist_agent = therapist_agent or TherapistAgent()
        self.intake_agent = intake_agent or IntakeAgent()

    async def start_session(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> str | None:
        """
        Start new therapy session for user.
        Returns greeting message, or None if prescreening is required first.
        """
        account_id = 0
        session_id = 0
        new_session_number = 1
        user_profile: dict | None = None
        flow_phase = "therapy"

        async with get_db_session() as session:
            account_repo = AccountRepository(session)
            session_repo = SessionRepository(session)
            pref_repo = TherapistPreferenceRepository(session)
            profile_repo = UserProfileRepository(session)

            # Get or create account (new schema)
            account = await account_repo.get_by_telegram_id(telegram_id)
            if not account:
                account = await account_repo.create_from_telegram(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code,
                )
                logger.info("new_account_created", account_id=account.id, telegram_id=telegram_id)
                # New user needs prescreening
                return None

            # Check if prescreening is completed
            is_prescreening_complete = await pref_repo.is_prescreening_complete(account.id)
            if not is_prescreening_complete:
                logger.info("prescreening_required", account_id=account.id)
                return None

            # Load user profile from new schema
            profile = await profile_repo.get_by_account_id(account.id)
            pref = await pref_repo.get_by_account_id(account.id)

            user_profile = {
                "therapist_name": (pref.therapist_name if pref else None) or "Опора",
                "therapist_gender": (pref.therapist_gender if pref else None) or "female",
                "therapist_traits": (pref.therapist_traits if pref else None) or [],
                "patient_display_name": (profile.effective_display_name if profile else None) or "",
                "patient_age": profile.age if profile else None,
                # NEW: Include sex and address_mode
                "patient_sex": (profile.sex if profile else None) or "prefer_not_to_say",
                "address_mode": (profile.address_mode if profile else None) or "formal",
            }

            # Check for active session
            active_session = await session_repo.get_active_session(account.id)
            if active_session:
                logger.info(
                    "existing_active_session",
                    account_id=account.id,
                    session_id=active_session.id,
                )
                # End existing session
                await session_repo.end_session(active_session.id)

            # Get latest session number
            latest_session = await session_repo.get_latest_session(account.id)
            if latest_session:
                new_session_number = latest_session.session_number + 1

            flow_phase = "intake" if self.settings.intake_enabled else "therapy"

            # Create DB session first to reserve stable session_id for stateless flow
            new_session = await session_repo.create_session(
                account_id=account.id,
                session_number=new_session_number,
                therapy_type="unspecified therapy",
                therapy_reason=None,
            )

            # Create intake state for the session
            intake_repo = IntakeStateRepository(session)
            await intake_repo.create_for_session(
                session_id=new_session.id,
                flow_phase=flow_phase,
            )

            account_id = account.id
            session_id = new_session.id

        # Build SessionState with user profile (NEW: includes sex and address_mode)
        state = SessionState(
            patient_id=str(account_id),
            session_id=f"{account_id}_{new_session_number}",
            session_db_id=session_id,
            dialog_count=0,
            session_counter=new_session_number,
            therapist_name=user_profile["therapist_name"],
            therapist_gender=user_profile["therapist_gender"],
            therapist_traits=user_profile["therapist_traits"],
            patient_display_name=user_profile["patient_display_name"],
            patient_age=user_profile["patient_age"],
            patient_sex=user_profile["patient_sex"],  # NEW
            address_mode=user_profile["address_mode"],  # NEW
            flow_phase=flow_phase,
            intake_user_turns=0,
        )

        # Determine which greeting branch to use based on card fill status
        card_filled = False
        async with get_db_session() as session:
            clinical_repo = ClinicalProfileRepository(session)
            card_filled = await clinical_repo.is_card_filled(account_id)

        if flow_phase == "intake":
            # Intake phase - check if card already has data
            if card_filled:
                # Card is filled - use welcome back message (even in intake phase)
                logger.info(
                    "start_branch_card_complete",
                    account_id=account_id,
                    session_id=session_id,
                    session_number=new_session_number,
                    flow_phase=flow_phase,
                )
                return self._build_welcome_back_message(
                    user_profile["patient_display_name"],
                    user_profile["address_mode"],  # NEW
                    user_profile["therapist_gender"],
                )
            else:
                # Card not filled - scripted intake message (no LLM)
                logger.info(
                    "start_branch_card_incomplete",
                    account_id=account_id,
                    session_id=session_id,
                    session_number=new_session_number,
                    flow_phase=flow_phase,
                )
                return self._build_intake_start_message(
                    user_profile["patient_display_name"],
                    user_profile["address_mode"],  # NEW
                    user_profile["therapist_gender"],
                )

        # Run async agent initialization with explicit state DTO
        agent_result = await self.therapist_agent.start_new_session(state)
        therapy_type = agent_result.get("current_therapy", "unspecified therapy")

        async with get_db_session() as session:
            session_repo = SessionRepository(session)
            await session_repo.update_therapy(
                session_id=session_id,
                therapy_type=therapy_type,
                therapy_reason=agent_result.get("reason", ""),
            )

            logger.info(
                "session_started",
                account_id=account_id,
                session_id=session_id,
                session_number=new_session_number,
                therapy=therapy_type,
            )

            return agent_result["therapist_response"]

    def _build_intake_start_message(
        self,
        patient_name: str,
        address_mode: str = "formal",  # NEW
        therapist_gender: str = "female",
    ) -> str:
        """Build scripted message for intake phase when card is NOT filled."""
        name_part = f"{patient_name}, " if patient_name else ""
        tg = therapist_gender if therapist_gender in ("female", "male") else "female"
        is_female = tg == "female"
        mog = "могла" if is_female else "мог"
        polezn = "полезной" if is_female else "полезным"

        if address_mode == "informal":
            # Informal (ты)
            return (
                f"{name_part}чтобы я {mog} лучше понимать тебя и эффективнее помогать, "
                "мне нужно собрать некоторую информацию о твоем состоянии. "
                f"Это поможет мне быть более {polezn} в наших беседах.\n\n"
                "Расскажи, пожалуйста, что сейчас беспокоит тебя больше всего?"
            )
        else:
            # Formal (вы) - default
            return (
                f"{name_part}чтобы я {mog} лучше понимать вас и эффективнее помогать, "
                "мне нужно собрать некоторую информацию о вашем состоянии. "
                f"Это поможет мне быть более {polezn} в наших беседах.\n\n"
                "Расскажите, пожалуйста, что сейчас беспокоит вас больше всего?"
            )

    def _build_welcome_back_message(
        self,
        patient_name: str,
        address_mode: str = "formal",  # NEW
        therapist_gender: str = "female",
    ) -> str:
        """Build welcome back message when card IS already filled."""
        name = patient_name or "друг"
        tg = therapist_gender if therapist_gender in ("female", "male") else "female"
        glad = "Рада" if tg == "female" else "Рад"

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

    async def create_session_silent(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> bool:
        """
        Silently create therapy session without returning greeting.
        Used internally after prescreening completion.
        Returns True if session created successfully.
        """
        async with get_db_session() as session:
            account_repo = AccountRepository(session)
            session_repo = SessionRepository(session)
            pref_repo = TherapistPreferenceRepository(session)
            intake_repo = IntakeStateRepository(session)

            # Get account
            account = await account_repo.get_by_telegram_id(telegram_id)
            if not account:
                logger.warning("silent_session_account_not_found", telegram_id=telegram_id)
                return False

            # Check prescreening completion
            is_prescreening_complete = await pref_repo.is_prescreening_complete(account.id)
            if not is_prescreening_complete:
                logger.warning("silent_session_prescreening_incomplete", account_id=account.id)
                return False

            # Check for and close any existing active session
            active_session = await session_repo.get_active_session(account.id)
            if active_session:
                await session_repo.end_session(active_session.id)
                logger.info("silent_session_closed_existing", account_id=account.id, session_id=active_session.id)

            # Get latest session number
            latest_session = await session_repo.get_latest_session(account.id)
            new_session_number = (latest_session.session_number + 1) if latest_session else 1

            flow_phase = "intake" if self.settings.intake_enabled else "therapy"

            # Create new session
            new_session = await session_repo.create_session(
                account_id=account.id,
                session_number=new_session_number,
                therapy_type="unspecified therapy",
                therapy_reason=None,
            )

            # Create intake state
            await intake_repo.create_for_session(
                session_id=new_session.id,
                flow_phase=flow_phase,
            )

            logger.info(
                "silent_session_created",
                account_id=account.id,
                telegram_id=telegram_id,
                session_id=new_session.id,
                session_number=new_session_number,
                flow_phase=flow_phase,
            )
            return True

    async def process_message(
        self,
        telegram_id: int,
        text: str,
    ) -> dict:
        """Process user message and return response."""
        async with trace_scope(
            name="telegram_dialog_turn",
            user_id=str(telegram_id),
        ) as trace:
            async with get_db_session() as session:
                account_repo = AccountRepository(session)
                session_repo = SessionRepository(session)
                message_repo = MessageRepository(session)
                pref_repo = TherapistPreferenceRepository(session)
                profile_repo = UserProfileRepository(session)
                intake_repo = IntakeStateRepository(session)

                # Get account
                account = await account_repo.get_by_telegram_id(telegram_id)
                if not account:
                    logger.warning("account_not_found", telegram_id=telegram_id)
                    return {
                        "response": "Please start with /start command first.",
                        "session_ended": False,
                    }

                # Check if prescreening is completed
                is_prescreening_complete = await pref_repo.is_prescreening_complete(account.id)
                if not is_prescreening_complete:
                    logger.info("prescreening_required_for_message", account_id=account.id)
                    return {
                        "response": "Пожалуйста, завершите настройку профиля. Нажмите /start для начала.",
                        "session_ended": False,
                    }

                # Get active session
                active_session = await session_repo.get_active_session(account.id)
                if not active_session:
                    logger.warning("no_active_session", account_id=account.id)
                    return {
                        "response": "No active session. Please start with /start.",
                        "session_ended": False,
                    }

                # Per-session transaction lock to avoid concurrent state races.
                await session_repo.acquire_session_lock(active_session.id)

                # Get user profile data
                profile = await profile_repo.get_by_account_id(account.id)
                pref = await pref_repo.get_by_account_id(account.id)
                intake_state = await intake_repo.get_by_session_id(active_session.id)

                # Build SessionState with user profile (NEW: includes sex and address_mode)
                state = SessionState(
                    patient_id=str(account.id),
                    session_id=f"{account.id}_{active_session.session_number}",
                    session_db_id=active_session.id,
                    dialog_count=active_session.dialog_count,
                    session_counter=active_session.session_number,
                    current_therapy=active_session.therapy_type,
                    current_stage=active_session.current_stage or "",
                    therapist_name=(pref.therapist_name if pref else None) or "Опора",
                    therapist_gender=(pref.therapist_gender if pref else None) or "female",
                    therapist_traits=(pref.therapist_traits if pref else None) or [],
                    patient_display_name=(profile.effective_display_name if profile else None) or "",
                    patient_age=profile.age if profile else None,
                    patient_sex=(profile.sex if profile else None) or "prefer_not_to_say",  # NEW
                    address_mode=(profile.address_mode if profile else None) or "formal",  # NEW
                    flow_phase=(intake_state.flow_phase if intake_state else "therapy"),
                    intake_user_turns=(intake_state.user_turn_count if intake_state else 0),
                )

                # Save user message
                msg_count = await message_repo.get_message_count(active_session.id)
                await message_repo.create_message(
                    session_id=active_session.id,
                    role="patient",
                    content=text,
                    message_number=msg_count + 1,
                )

                if state.flow_phase == "intake":
                    result = await self.intake_agent.process_patient_input(
                        patient_text=text,
                        state=state,
                    )
                    await message_repo.create_message(
                        session_id=active_session.id,
                        role="doctor",
                        content=result["therapist_response"],
                        message_number=msg_count + 2,
                    )
                    await session_repo.increment_dialog_count(active_session.id)

                    # Update intake state
                    updated_intake = await intake_repo.increment_turns(active_session.id)
                    intake_turns_after = (
                        updated_intake.user_turn_count
                        if updated_intake
                        else state.intake_user_turns + 1
                    )

                    if result.get("intake_completed"):
                        await intake_repo.mark_completed(active_session.id)
                        logger.info(
                            "flow_phase_switched",
                            account_id=account.id,
                            session_id=active_session.id,
                            previous_phase="intake",
                            new_phase="therapy",
                            intake_user_turns=intake_turns_after,
                        )
                    else:
                        logger.info(
                            "intake_turn_processed",
                            account_id=account.id,
                            session_id=active_session.id,
                            intake_user_turns=intake_turns_after,
                            missing_fields=result.get("missing_fields", []),
                        )

                    LangfuseClient().update_trace(
                        trace=trace,
                        metadata={
                            "flow_phase": "intake",
                            "intake_user_turns": intake_turns_after,
                            "intake_completed": bool(result.get("intake_completed", False)),
                        },
                    )
                    return {
                        "response": result["therapist_response"],
                        "session_ended": False,
                        "strategy": {},
                    }

                # Process through therapy agent (legacy logic preserved)
                patient_response = {
                    "text": text,
                    "attitude": "neutral",  # Simplified - determined by evaluator
                }

                result = await self.therapist_agent.process_patient_input(
                    patient_response=patient_response,
                    state=state,
                )

                await message_repo.create_message(
                    session_id=active_session.id,
                    role="doctor",
                    content=result["therapist_response"],
                    message_number=msg_count + 2,
                    primary_emotion=result.get("strategy", {}).get("primary_emotion"),
                )

                await session_repo.increment_dialog_count(state.session_db_id or active_session.id)

                await session_repo.update_therapy(
                    session_id=active_session.id,
                    therapy_type=result.get("current_therapy", state.current_therapy),
                )
                if state.current_stage:
                    await session_repo.update_current_stage(
                        session_id=active_session.id,
                        stage=state.current_stage,
                    )

                if (
                    self.settings.intake_background_update_enabled
                    and self.settings.intake_background_update_every_user_turns > 0
                ):
                    current_user_turn = state.dialog_count + 1
                    if current_user_turn % self.settings.intake_background_update_every_user_turns == 0:
                        card_updates = await self.intake_agent.update_card_from_message(
                            patient_text=text,
                            state=state,
                        )
                        if card_updates:
                            logger.info(
                                "intake_card_updated",
                                account_id=account.id,
                                session_id=active_session.id,
                                updated_fields=sorted(card_updates.keys()),
                            )

                if result.get("session_ended"):
                    await session_repo.end_session(active_session.id)

                logger.info(
                    "message_processed",
                    account_id=account.id,
                    session_id=active_session.id,
                    session_ended=result.get("session_ended", False),
                )

                LangfuseClient().update_trace(
                    trace=trace,
                    metadata={
                        "flow_phase": "therapy",
                        "session_ended": bool(result.get("session_ended", False)),
                    },
                )
                return {
                    "response": result["therapist_response"],
                    "session_ended": result.get("session_ended", False),
                    "strategy": result.get("strategy", {}),
                }

    async def get_patient_summary(self, telegram_id: int) -> str:
        """Return patient card summary text without LLM usage."""
        async with get_db_session() as session:
            account_repo = AccountRepository(session)
            session_repo = SessionRepository(session)
            pref_repo = TherapistPreferenceRepository(session)
            clinical_repo = ClinicalProfileRepository(session)
            profile_repo = UserProfileRepository(session)

            account = await account_repo.get_by_telegram_id(telegram_id)
            if not account:
                return "Профиль не найден. Нажмите /start для начала."

            is_prescreening_complete = await pref_repo.is_prescreening_complete(account.id)
            if not is_prescreening_complete:
                return "Сначала завершите прескрининг через /start."

            # Get clinical profile
            card = await clinical_repo.get_patient_record(account.id)
            active_session = await session_repo.get_active_session(account.id)

            intake_state = None
            if active_session:
                intake_repo = IntakeStateRepository(session)
                intake_state = await intake_repo.get_by_session_id(active_session.id)

            flow_phase = intake_state.flow_phase if intake_state else "therapy"

            # Get profile data
            profile = await profile_repo.get_by_account_id(account.id)

            if not card:
                if flow_phase == "intake":
                    return "Карточка пока в процессе заполнения. Продолжайте отвечать в текущем диалоге."
                return "Карточка пока не содержит данных."

            has_any_data = any(
                card.get(key, "").strip()
                for key in (
                    "mental_health_history",
                    "physical_health_history",
                    "current_problems",
                    "intake_hypothesis",
                    "intake_hypothesis_explanation",
                )
            )
            if not has_any_data:
                if flow_phase == "intake":
                    return "Карточка пока в процессе заполнения. Продолжайте отвечать в текущем диалоге."
                return "Карточка пока не содержит данных."

            display_name = (profile.effective_display_name if profile else None) or "Пациент"
            age = str(profile.age) if profile and profile.age else "не указан"

            # NEW: Include sex in summary
            sex_display = profile.sex_display if profile else "Не указан"

            return (
                f"Сводка карточки пациента\n\n"
                f"Имя/псевдоним: {display_name}\n"
                f"Возраст: {age}\n"
                f"Пол: {sex_display}\n\n"  # NEW
                f"История психического здоровья:\n{card.get('mental_health_history') or 'не указано'}\n\n"
                f"История физического здоровья:\n{card.get('physical_health_history') or 'не указано'}\n\n"
                f"Текущие проблемы и симптомы:\n{card.get('current_problems') or 'не указано'}\n\n"
                f"Предварительная клиническая гипотеза:\n{card.get('intake_hypothesis') or 'не указано'}\n\n"
                f"Пояснение:\n{card.get('intake_hypothesis_explanation') or 'не указано'}"
            )

    def _get_trait_labels_russian(self, trait_ids: list[str]) -> list[str]:
        """Convert trait IDs to Russian labels."""
        trait_map = {
            "strict": "Строгий",
            "business": "Деловой",
            "calm": "Спокойный",
            "kind": "Добрый",
            "restrained": "Сдержанный",
            "empathetic": "Эмпатичный",
        }
        return [trait_map.get(tid, tid) for tid in trait_ids]

    async def get_user_anket(self, telegram_id: int) -> str:
        """Return user prescreening profile (anket) for display - with NEW fields (sex, address_mode)."""
        async with get_db_session() as session:
            account_repo = AccountRepository(session)
            pref_repo = TherapistPreferenceRepository(session)
            profile_repo = UserProfileRepository(session)

            account = await account_repo.get_by_telegram_id(telegram_id)
            if not account:
                return "Профиль не найден. Нажмите /start для начала."

            is_prescreening_complete = await pref_repo.is_prescreening_complete(account.id)
            if not is_prescreening_complete:
                return "Сначала завершите настройку профиля через /start."

            # Get therapist preferences
            pref = await pref_repo.get_by_account_id(account.id)
            therapist_profile = pref.get_therapist_profile() if pref else {"name": "Опора", "gender": "female", "traits": []}

            # Build anket display with Russian trait labels
            traits = therapist_profile.get("traits", [])
            traits_labels = self._get_trait_labels_russian(traits)
            traits_str = ", ".join(traits_labels) if traits_labels else "не указаны"
            gender = "Женский" if therapist_profile.get("gender") == "female" else "Мужской"

            # Get user profile (with NEW fields)
            profile = await profile_repo.get_by_account_id(account.id)
            display_name = (profile.effective_display_name if profile else None) or "не указано"
            age = str(profile.age) if profile and profile.age else "не указан"

            # NEW: Get sex and address_mode
            sex_display = profile.sex_display if profile else "Не указан"
            address_display = profile.address_mode_display if profile else "На 'Вы'"

            # Enhanced format with NEW fields
            return (
                f"📋 <b>Ваша анкета</b>\n\n"
                f"<b>Настройки психолога:</b>\n"
                f"🧠 Имя: {therapist_profile.get('name', 'Опора')}\n"
                f"⚧ Пол: {gender}\n"
                f"✨ Черты: {traits_str}\n\n"
                f"<b>Ваши данные:</b>\n"
                f"👤 Имя: {display_name}\n"
                f"🎂 Возраст: {age}\n"
                f"⚥ Пол: {sex_display}\n"  # NEW
                f"💬 Обращение: {address_display}"  # NEW
            )

    async def reset_user_data(self, telegram_id: int) -> bool:
        """Delete user account and all associated data from database.
        
        Returns True if user was found and deleted, False if user not found.
        All related data (profiles, sessions, messages, logs) is deleted
        via CASCADE constraints.
        """
        async with get_db_session() as session:
            account_repo = AccountRepository(session)
            deleted = await account_repo.delete_by_telegram_id(telegram_id)
            
            if deleted:
                logger.info(
                    "user_data_reset_complete",
                    telegram_id=telegram_id,
                )
            else:
                logger.warning(
                    "user_data_reset_not_found",
                    telegram_id=telegram_id,
                )
            
            return deleted
