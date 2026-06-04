"""Main therapist agent for Opora dialogue generation."""

from typing import Any, Dict

from core.config import get_settings
from core.logging import get_logger, LogContexts
from agents.prompts.therapist_prompts import TherapistPrompts
from db.session import get_db_session
from db.repositories import (
    AccountRepository,
    ClinicalProfileRepository,
    SessionRepository,
    MessageRepository,
    DecisionLogRepository,
)
from services.llm import LlmGateway
from .session_state import SessionState

logger = get_logger(LogContexts.AGENT)

DEFAULT_THERAPY = "cognitive-behavioral therapy"


class TherapistAgent:
    """Main therapist agent for Opora."""

    def __init__(self):
        self.settings = get_settings()
        self.llm_gateway = LlmGateway()

    async def start_new_session(self, state: SessionState) -> Dict[str, Any]:
        """Start new therapy session and return greeting."""
        patient_id = state.patient_id
        account_id_int = int(patient_id)

        async with get_db_session() as session:
            account_repo = AccountRepository(session)
            account = await account_repo.get_by_id(account_id_int)
            if not account:
                account = await account_repo.create_from_telegram(
                    telegram_id=account_id_int,
                )

        state.current_therapy = DEFAULT_THERAPY
        state.dialog_count = 0
        state.current_stage = ""

        if state.session_counter == 1:
            greeting = TherapistPrompts.get_first_session_greeting(
                therapist_name=state.therapist_name,
                patient_display_name=state.patient_display_name,
                language="ru",
                address_mode=state.address_mode,
            )
        else:
            greeting = TherapistPrompts.get_return_session_greeting(
                therapist_name=state.therapist_name,
                patient_display_name=state.patient_display_name,
                language="ru",
                address_mode=state.address_mode,
            )

        async with get_db_session() as session:
            decision_repo = DecisionLogRepository(session)
            await decision_repo.log_decision(
                session_id=state.session_db_id or 0,
                response_number=0,
                current_therapy=state.current_therapy,
            )

        return {
            "patient_id": patient_id,
            "session_id": state.session_id,
            "therapist_response": greeting,
            "current_therapy": state.current_therapy,
            "reason": "",
        }

    async def process_patient_input(
        self,
        patient_response: Dict[str, Any],
        state: SessionState,
    ) -> Dict[str, Any]:
        """Process patient input and generate response."""
        patient_text = patient_response["text"]

        if not state.session_id:
            return {
                "therapist_response": "There is no active session.",
                "session_ended": False,
                "current_therapy": "unspecified therapy",
                "strategy": {"strategy": "", "strategy_text": ""},
            }

        state.dialog_count += 1
        user_id_int = int(state.patient_id) if state.patient_id else 0

        current_stage = state.current_stage
        if state.session_db_id:
            async with get_db_session() as session:
                session_repo = SessionRepository(session)
                current_session = await session_repo.get_by_id(state.session_db_id)
                if current_session and current_session.current_stage:
                    current_stage = current_session.current_stage
                    state.current_stage = current_stage

        strategy = {
            "strategy": "",
            "strategy_text": "",
            "active_style": (state.therapist_styles or ["friendly"])[0],
        }
        emotion_data = {
            "primary_emotion": "",
            "emotional_intensity": 0.0,
        }

        response = await self._generate_response(
            patient_input=patient_text,
            emotion_data=emotion_data,
            current_therapy=state.current_therapy or DEFAULT_THERAPY,
            current_stage=current_stage,
            strategy=strategy,
            memory_result="No",
            user_id=user_id_int,
            state=state,
        )

        async with get_db_session() as session:
            decision_repo = DecisionLogRepository(session)
            await decision_repo.log_decision(
                session_id=state.session_db_id or 0,
                response_number=state.dialog_count,
                memory_invoke_result="No",
                is_rejecting=False,
                current_therapy=state.current_therapy,
                current_stage=current_stage,
                response_strategy=strategy.get("strategy"),
                strategy_description=strategy.get("strategy_text"),
                patient_attitude=patient_response.get("attitude", "neutral"),
            )

        return {
            "therapist_response": response,
            "session_ended": False,
            "current_therapy": state.current_therapy,
            "strategy": strategy,
        }

    async def _generate_response(
        self,
        patient_input: str,
        emotion_data: Dict[str, Any],
        current_therapy: str,
        current_stage: str,
        strategy: Dict[str, str],
        memory_result: str,
        user_id: int,
        state: SessionState,
    ) -> str:
        """Generate therapist response."""
        session_memory = {"dialogs": []}
        if state.session_id and state.session_db_id:
            async with get_db_session() as session:
                msg_repo = MessageRepository(session)
                try:
                    messages = await msg_repo.get_latest_messages(
                        state.session_db_id,
                        count=10,
                    )
                    dialogs = [
                        f"{'PATIENT' if m.role == 'patient' else 'DOCTOR'}: {m.content}"
                        for m in messages
                    ]
                    session_memory = {"dialogs": dialogs}
                except Exception:
                    pass

        primary_emotion = emotion_data.get("primary_emotion", "")
        emotional_intensity = emotion_data.get("emotional_intensity", 0.0)
        current_strategy = strategy.get("strategy", "")
        current_strategy_text = strategy.get("strategy_text", "")
        active_style = strategy.get("active_style")

        system_message = TherapistPrompts.get_system_message(
            therapist_name=state.therapist_name,
            therapist_gender=state.therapist_gender,
            therapist_styles=state.therapist_styles,
            address_mode=state.address_mode,
        )

        prompt_variables = {
            "patient_input": patient_input,
            "memory_result": memory_result,
            "primary_emotion": primary_emotion,
            "emotional_intensity": emotional_intensity,
            "current_therapy": current_therapy,
            "current_stage": current_stage,
            "current_strategy": current_strategy,
            "current_strategy_text": current_strategy_text,
            "active_style": active_style,
            "session_memory": session_memory,
            "therapist_name": state.therapist_name,
            "patient_display_name": state.patient_display_name,
            "patient_age": state.patient_age,
            "patient_sex": state.patient_sex,
            "therapist_styles": state.therapist_styles,
            "address_mode": state.address_mode,
        }

        prompt = TherapistPrompts.get_response_prompt(
            patient_input=patient_input,
            memory_result=memory_result,
            primary_emotion=primary_emotion,
            emotional_intensity=emotional_intensity,
            current_therapy=current_therapy,
            current_stage=current_stage,
            current_strategy=current_strategy,
            current_strategy_text=current_strategy_text,
            session_memory=session_memory,
            therapist_name=state.therapist_name,
            patient_display_name=state.patient_display_name,
            patient_age=state.patient_age,
            patient_sex=state.patient_sex,
            therapist_styles=state.therapist_styles,
            address_mode=state.address_mode,
            active_style=active_style,
        )

        prompt_messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]
        result = await self.llm_gateway.complete(
            agent_type="therapist",
            task_name="generate_response",
            messages=prompt_messages,
            account_id=user_id,
            session_id=state.session_db_id,
            prompt=prompt,
            prompt_template="TherapistPrompts.get_response_prompt",
            prompt_variables=prompt_variables,
        )

        if result["success"]:
            raw_response = result["content"]
            clean_response = raw_response.replace('\\"', '"')
            return clean_response.strip('"')

        return TherapistPrompts.get_fallback_response(
            language="ru",
            address_mode=state.address_mode,
        )
