"""Dialogue orchestration service."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from agents.core import IntakeAgent, TherapistAgent
from core.config import get_settings
from core.clinical_card_format import card_has_clinical_data, format_full_patient_summary
from core.intake_user_copy import (
    build_intake_completion_notice,
    build_intake_extracted_summary,
    build_intake_start_message,
    build_welcome_back_message,
)
from core.logging import LogContexts, get_logger
from core.profile_labels import address_mode_label, sex_label, style_labels
from db.repositories import (
    AccountRepository,
    ClinicalProfileRepository,
    ConversationTraceRepository,
    IntakeStateRepository,
    MessageRepository,
    SessionRepository,
)
from db.session import get_db_session
from observability.tracing import TraceContext, get_current_trace, trace_scope
from services.prescreening_gate import evaluate_prescreening_gate
from services.session_lifecycle import get_or_create_active_session
from services.session_state_builder import build_session_state
from services.user_context import load_user_context

logger = get_logger(LogContexts.SERVICE)


class DialogueService:
    """Top-level orchestrator for dialogue flows."""

    def __init__(
        self,
        therapist_agent: TherapistAgent | None = None,
        intake_agent: IntakeAgent | None = None,
    ) -> None:
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
        channel: str = "telegram",
        source: str = "bot",
    ) -> str | None:
        """Start new session with an end-to-end observability trace."""
        if get_current_trace():
            return await self._start_session_core(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
            )

        trace = TraceContext(channel=channel, source=source)
        started = time.perf_counter()
        status = "success"
        error_message: str | None = None
        with trace_scope(trace):
            try:
                return await self._start_session_core(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code,
                )
            except Exception as exc:
                status = "error"
                error_message = str(exc)
                raise
            finally:
                finished_at = datetime.now(timezone.utc)
                duration_ms = int((time.perf_counter() - started) * 1000)
                try:
                    async with get_db_session() as session:
                        trace_repo = ConversationTraceRepository(session)
                        await trace_repo.create_from_context(
                            trace=trace,
                            status=status,
                            finished_at=finished_at,
                            duration_ms=duration_ms,
                            error_message=error_message,
                        )
                except Exception as trace_error:
                    logger.warning("conversation_trace_persist_failed", error=str(trace_error))

    async def _start_session_core(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> str | None:
        """Start new session and return greeting or intake opener."""
        async with get_db_session() as session:
            account_repo = AccountRepository(session)
            gate = await evaluate_prescreening_gate(telegram_id, session)

            if not gate.account_exists:
                account = await account_repo.create_from_telegram(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code,
                )
                current_trace = get_current_trace()
                if current_trace:
                    current_trace.account_id = account.id
                logger.info("new_account_created", account_id=account.id, telegram_id=telegram_id)
                return None

            if not gate.is_complete or gate.account_id is None:
                logger.info("prescreening_required", telegram_id=telegram_id)
                return None

            context = await load_user_context(gate.account_id, session)
            current_trace = get_current_trace()
            if current_trace:
                current_trace.account_id = context.account_id
            created = await get_or_create_active_session(
                account_id=context.account_id,
                intake_enabled=self.settings.intake_enabled,
                session=session,
            )
            if current_trace:
                current_trace.session_id = created.session_id

            state = build_session_state(
                context=context,
                session_number=created.session_number,
                session_db_id=created.session_id,
                flow_phase=created.flow_phase,
            )

        if not created.created_new:
            if created.flow_phase == "intake":
                return build_intake_start_message(
                    context.patient_display_name,
                    context.address_mode,
                    context.therapist_gender,
                    self.settings.intake_min_user_turns,
                    self.settings.intake_max_user_turns,
                )
            return build_welcome_back_message(
                context.patient_display_name,
                context.address_mode,
                context.therapist_gender,
            )

        if created.flow_phase == "intake":
            return build_intake_start_message(
                context.patient_display_name,
                context.address_mode,
                context.therapist_gender,
                self.settings.intake_min_user_turns,
                self.settings.intake_max_user_turns,
            )

        if context.card_filled and self.settings.intake_enabled:
            return build_welcome_back_message(
                context.patient_display_name,
                context.address_mode,
                context.therapist_gender,
            )

        agent_result = await self.therapist_agent.start_new_session(state)
        therapy_type = agent_result.get("current_therapy", "unspecified therapy")
        async with get_db_session() as session:
            session_repo = SessionRepository(session)
            await session_repo.update_therapy(
                session_id=created.session_id,
                therapy_type=therapy_type,
                therapy_reason=agent_result.get("reason", ""),
            )
        return agent_result["therapist_response"]

    async def create_session_silent(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> bool:
        """Create a new session without producing a greeting."""
        _ = (username, first_name, last_name, language_code)
        async with get_db_session() as session:
            gate = await evaluate_prescreening_gate(telegram_id, session)
            if not gate.account_exists or not gate.is_complete or gate.account_id is None:
                return False
            await get_or_create_active_session(
                account_id=gate.account_id,
                intake_enabled=self.settings.intake_enabled,
                session=session,
            )
            return True

    async def process_message(
        self,
        telegram_id: int,
        text: str,
        channel: str = "telegram",
        source: str = "bot",
    ) -> dict:
        """Process user message with an end-to-end observability trace."""
        if get_current_trace():
            return await self._process_message_core(telegram_id=telegram_id, text=text)

        trace = TraceContext(channel=channel, source=source)
        started = time.perf_counter()
        status = "success"
        error_message: str | None = None
        with trace_scope(trace):
            try:
                result = await self._process_message_core(telegram_id=telegram_id, text=text)
                if isinstance(result, dict):
                    result.setdefault(
                        "trace",
                        {
                            "trace_id": str(trace.trace_id),
                            "turn_id": str(trace.turn_id),
                            "channel": trace.channel,
                        },
                    )
                return result
            except Exception as exc:
                status = "error"
                error_message = str(exc)
                raise
            finally:
                finished_at = datetime.now(timezone.utc)
                duration_ms = int((time.perf_counter() - started) * 1000)
                try:
                    async with get_db_session() as session:
                        trace_repo = ConversationTraceRepository(session)
                        await trace_repo.create_from_context(
                            trace=trace,
                            status=status,
                            finished_at=finished_at,
                            duration_ms=duration_ms,
                            error_message=error_message,
                        )
                except Exception as trace_error:
                    logger.warning("conversation_trace_persist_failed", error=str(trace_error))

    async def _process_message_core(
        self,
        telegram_id: int,
        text: str,
    ) -> dict:
        """Process user message and return response."""
        async with get_db_session() as session:
            gate = await evaluate_prescreening_gate(telegram_id, session)
            if not gate.account_exists or gate.account_id is None:
                return {
                    "response": "Please start with /start command first.",
                    "session_ended": False,
                }
            if not gate.is_complete:
                return {
                    "response": "Пожалуйста, завершите настройку профиля. Нажмите /start для начала.",
                    "session_ended": False,
                }

            account_id = gate.account_id
            current_trace = get_current_trace()
            if current_trace:
                current_trace.account_id = account_id
            # Get active session
            session_repo = SessionRepository(session)
            message_repo = MessageRepository(session)
            intake_repo = IntakeStateRepository(session)
            active_session = await session_repo.get_active_session(account_id)
            if not active_session:
                logger.warning("no_active_session", account_id=account_id)
                return {
                    "response": "No active session. Please start with /start.",
                    "session_ended": False,
                }
            if current_trace:
                current_trace.session_id = active_session.id

            # Per-session transaction lock to avoid concurrent state races.
            await session_repo.acquire_session_lock(active_session.id)

            context = await load_user_context(account_id, session)
            intake_state = await intake_repo.get_by_session_id(active_session.id)

            state = build_session_state(
                context=context,
                session_number=active_session.session_number,
                session_db_id=active_session.id,
                dialog_count=active_session.dialog_count,
                current_therapy=active_session.therapy_type,
                current_stage=active_session.current_stage or "",
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
                therapist_closure = result["therapist_response"]
                doctor_content = therapist_closure
                closure_segments = None
                if result.get("intake_completed"):
                    extracted = build_intake_extracted_summary(
                        result.get("card_updates") or {},
                        address_mode=state.address_mode,
                        initial_info_insufficient=bool(
                            result.get("initial_info_insufficient")
                        ),
                        max_words=self.settings.intake_summary_max_words,
                    )
                    notice = build_intake_completion_notice(
                        state.address_mode,
                        bool(result.get("initial_info_insufficient")),
                    )
                    closure_segments = {
                        "therapist_closure": therapist_closure,
                        "extracted_summary": extracted,
                        "completion_notice": notice,
                    }
                    doctor_content = f"{therapist_closure}\n\n{extracted}\n\n{notice}".strip()
                await message_repo.create_message(
                    session_id=active_session.id,
                    role="doctor",
                    content=doctor_content,
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
                        account_id=account_id,
                        session_id=active_session.id,
                        previous_phase="intake",
                        new_phase="therapy",
                        intake_user_turns=intake_turns_after,
                    )
                else:
                    logger.info(
                        "intake_turn_processed",
                        account_id=account_id,
                        session_id=active_session.id,
                        intake_user_turns=intake_turns_after,
                        missing_fields=result.get("missing_fields", []),
                    )

                return {
                    "response": doctor_content,
                    "session_ended": False,
                    "intake_completed": bool(result.get("intake_completed")),
                    "closure_segments": closure_segments,
                    "initial_info_insufficient": bool(
                        result.get("initial_info_insufficient")
                    ),
                    "strategy": result.get("strategy", {}),
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

            logger.info(
                "message_processed",
                account_id=account_id,
                session_id=active_session.id,
                session_ended=False,
            )

            return {
                "response": result["therapist_response"],
                "session_ended": False,
                "strategy": result.get("strategy", {}),
            }

    async def get_patient_summary(self, telegram_id: int) -> str:
        """Return patient card summary text without LLM usage."""
        async with get_db_session() as session:
            session_repo = SessionRepository(session)
            clinical_repo = ClinicalProfileRepository(session)
            gate = await evaluate_prescreening_gate(telegram_id, session)
            if not gate.account_exists or gate.account_id is None:
                return "Профиль не найден. Нажмите /start для начала."
            if not gate.is_complete:
                return "Сначала завершите прескрининг через /start."

            # Get clinical profile
            card = await clinical_repo.get_patient_record(gate.account_id)
            active_session = await session_repo.get_active_session(gate.account_id)

            intake_state = None
            if active_session:
                intake_repo = IntakeStateRepository(session)
                intake_state = await intake_repo.get_by_session_id(active_session.id)

            flow_phase = intake_state.flow_phase if intake_state else "therapy"

            # Get profile data
            context = await load_user_context(gate.account_id, session)

            if not card:
                if flow_phase == "intake":
                    return "Карточка пока в процессе заполнения. Продолжайте отвечать в текущем диалоге."
                return "Карточка пока не содержит данных."

            has_any_data = card_has_clinical_data(card)
            if not has_any_data:
                if flow_phase == "intake":
                    return "Карточка пока в процессе заполнения. Продолжайте отвечать в текущем диалоге."
                return "Карточка пока не содержит данных."

            display_name = context.patient_display_name or "Пациент"
            age = str(context.patient_age) if context.patient_age else "не указан"
            sex_display = sex_label(context.patient_sex)

            return format_full_patient_summary(
                card=card,
                display_name=display_name,
                age=age,
                sex_display=sex_display,
            )

    async def get_user_anket(self, telegram_id: int) -> str:
        """Return user prescreening profile."""
        async with get_db_session() as session:
            gate = await evaluate_prescreening_gate(telegram_id, session)
            if not gate.account_exists or gate.account_id is None:
                return "Профиль не найден. Нажмите /start для начала."
            if not gate.is_complete:
                return "Сначала завершите настройку профиля через /start."

            context = await load_user_context(gate.account_id, session)
            styles_labels = style_labels(context.therapist_styles)
            styles_str = ", ".join(styles_labels) if styles_labels else "не указан"
            gender = "Женский" if context.therapist_gender == "female" else "Мужской"
            display_name = context.patient_display_name or "не указано"
            age = str(context.patient_age) if context.patient_age else "не указан"
            sex_display = sex_label(context.patient_sex)
            address_display = address_mode_label(context.address_mode)

            return (
                f"📋 <b>Ваша анкета</b>\n\n"
                f"<b>Настройки психолога:</b>\n"
                f"🧠 Имя: {context.therapist_name}\n"
                f"⚧ Пол: {gender}\n"
                f"✨ Стиль: {styles_str}\n\n"
                f"<b>Ваши данные:</b>\n"
                f"👤 Имя: {display_name}\n"
                f"🎂 Возраст: {age}\n"
                f"⚥ Пол: {sex_display}\n"
                f"💬 Обращение: {address_display}"
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
