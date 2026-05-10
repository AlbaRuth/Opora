"""
Dialogue service - main orchestrator for user interactions.
Coordinates between Telegram, Agents, and Database.
"""

from typing import Any

from agents.core import IntakeAgent, SessionState, TherapistAgent
from core.config import get_settings
from core.logging import get_logger, LogContexts
from db.repositories import UserRepository, SessionRepository, MessageRepository
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
        user_id = 0
        session_id = 0
        new_session_number = 1
        user_profile: dict | None = None
        flow_phase = "therapy"

        async with get_db_session() as session:
            user_repo = UserRepository(session)
            session_repo = SessionRepository(session)
            
            # Get or create user
            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                user = await user_repo.create_from_telegram(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code,
                )
                logger.info("new_user_created", user_id=user.id, telegram_id=telegram_id)
                # New user needs prescreening
                return None
            
            # Check if prescreening is completed
            if not user.is_prescreening_complete:
                logger.info("prescreening_required", user_id=user.id)
                return None
            
            # Load user profile for session
            user_profile = {
                "therapist_name": user.therapist_name or "Опора",
                "therapist_gender": user.therapist_gender or "female",
                "therapist_traits": user.therapist_traits or [],
                "patient_display_name": user.patient_display_name or user.patient_pseudonym or "",
                "patient_age": user.patient_age,
            }
            
            # Check for active session
            active_session = await session_repo.get_active_session(user.id)
            if active_session:
                logger.info(
                    "existing_active_session",
                    user_id=user.id,
                    session_id=active_session.id,
                )
                # End existing session
                await session_repo.end_session(active_session.id)
            
            # Get latest session number
            latest_session = await session_repo.get_latest_session(user.id)
            if latest_session:
                new_session_number = latest_session.session_number + 1

            flow_phase = "intake" if self.settings.intake_enabled else "therapy"
            
            # Create DB session first to reserve stable session_id for stateless flow
            new_session = await session_repo.create_session(
                user_id=user.id,
                session_number=new_session_number,
                therapy_type="unspecified therapy",
                therapy_reason=None,
                flow_phase=flow_phase,
            )
            user_id = user.id
            session_id = new_session.id

        # Build SessionState with user profile
        state = SessionState(
            patient_id=str(user_id),
            session_id=f"{user_id}_{new_session_number}",
            session_db_id=session_id,
            dialog_count=0,
            session_counter=new_session_number,
            therapist_name=user_profile["therapist_name"],
            therapist_gender=user_profile["therapist_gender"],
            therapist_traits=user_profile["therapist_traits"],
            patient_display_name=user_profile["patient_display_name"],
            patient_age=user_profile["patient_age"],
            flow_phase=flow_phase,
            intake_user_turns=0,
        )

        if flow_phase == "intake":
            logger.info(
                "intake_started",
                user_id=user_id,
                session_id=session_id,
                session_number=new_session_number,
            )
            return self._build_intake_start_message(user_profile["patient_display_name"])

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
                user_id=user_id,
                session_id=session_id,
                session_number=new_session_number,
                therapy=therapy_type,
            )
            
            return agent_result["therapist_response"]

    def _build_intake_start_message(self, patient_name: str) -> str:
        name_part = f"{patient_name}, " if patient_name else ""
        return (
            f"{name_part}рады знакомству. Сейчас коротко соберем информацию о вашем состоянии, "
            "чтобы я лучше понимала, как вам помочь. "
            "Расскажите, пожалуйста, что сейчас беспокоит вас сильнее всего."
        )
    
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
                user_repo = UserRepository(session)
                session_repo = SessionRepository(session)
                message_repo = MessageRepository(session)
                
                # Get user
                user = await user_repo.get_by_telegram_id(telegram_id)
                if not user:
                    logger.warning("user_not_found", telegram_id=telegram_id)
                    return {
                        "response": "Please start with /start command first.",
                        "session_ended": False,
                    }
                
                # Check if prescreening is completed
                if not user.is_prescreening_complete:
                    logger.info("prescreening_required_for_message", user_id=user.id)
                    return {
                        "response": "Пожалуйста, завершите настройку профиля. Нажмите /start для начала.",
                        "session_ended": False,
                    }
                
                # Get active session
                active_session = await session_repo.get_active_session(user.id)
                if not active_session:
                    logger.warning("no_active_session", user_id=user.id)
                    return {
                        "response": "No active session. Please start with /start.",
                        "session_ended": False,
                    }

                # Per-session transaction lock to avoid concurrent state races.
                await session_repo.acquire_session_lock(active_session.id)

                # Build SessionState with user profile
                state = SessionState(
                    patient_id=str(user.id),
                    session_id=f"{user.id}_{active_session.session_number}",
                    session_db_id=active_session.id,
                    dialog_count=active_session.dialog_count,
                    session_counter=active_session.session_number,
                    current_therapy=active_session.therapy_type,
                    current_stage=active_session.current_stage or "",
                    therapist_name=user.therapist_name or "Опора",
                    therapist_gender=user.therapist_gender or "female",
                    therapist_traits=user.therapist_traits or [],
                    patient_display_name=user.patient_display_name or user.patient_pseudonym or "",
                    patient_age=user.patient_age,
                    flow_phase=active_session.flow_phase or "therapy",
                    intake_user_turns=active_session.intake_user_turns or 0,
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
                    updated_session = await session_repo.increment_intake_turns(active_session.id)
                    intake_turns_after = (
                        updated_session.intake_user_turns
                        if updated_session
                        else state.intake_user_turns + 1
                    )

                    if result.get("intake_completed"):
                        await session_repo.mark_intake_completed(active_session.id)
                        logger.info(
                            "flow_phase_switched",
                            user_id=user.id,
                            session_id=active_session.id,
                            previous_phase="intake",
                            new_phase="therapy",
                            intake_user_turns=intake_turns_after,
                        )
                    else:
                        logger.info(
                            "intake_turn_processed",
                            user_id=user.id,
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
                                user_id=user.id,
                                session_id=active_session.id,
                                updated_fields=sorted(card_updates.keys()),
                            )

                if result.get("session_ended"):
                    await session_repo.end_session(active_session.id)

                logger.info(
                    "message_processed",
                    user_id=user.id,
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
            user_repo = UserRepository(session)
            session_repo = SessionRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if not user:
                return "Профиль не найден. Нажмите /start для начала."
            if not user.is_prescreening_complete:
                return "Сначала завершите прескрининг через /start."

            card = user.get_patient_record()
            active_session = await session_repo.get_active_session(user.id)
            flow_phase = active_session.flow_phase if active_session else "therapy"

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

            display_name = user.patient_display_name or user.patient_pseudonym or "Пациент"
            age = str(user.patient_age) if user.patient_age is not None else "не указан"
            return (
                f"Сводка карточки пациента\n\n"
                f"Имя/псевдоним: {display_name}\n"
                f"Возраст: {age}\n\n"
                f"История психического здоровья:\n{card.get('mental_health_history') or 'не указано'}\n\n"
                f"История физического здоровья:\n{card.get('physical_health_history') or 'не указано'}\n\n"
                f"Текущие проблемы и симптомы:\n{card.get('current_problems') or 'не указано'}\n\n"
                f"Предварительная клиническая гипотеза:\n{card.get('intake_hypothesis') or 'не указано'}\n\n"
                f"Пояснение:\n{card.get('intake_hypothesis_explanation') or 'не указано'}"
            )
