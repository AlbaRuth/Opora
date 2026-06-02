"""
TherapistAgent - preserved logic from original Opora.
Original implementation from agent/main.py lines 39-289.
"""

from typing import Any, Dict

from core.config import get_settings
from core.logging import get_logger, LogContexts
from integrations.openrouter import OpenRouterClient
from agents.prompts.therapist_prompts import TherapistPrompts
from agents.evaluators.therapist_evaluator import TherapistEvaluator
from db.session import get_db_session
from db.repositories import (
    AccountRepository,
    ClinicalProfileRepository,
    SessionRepository,
    MessageRepository,
    DecisionLogRepository,
    AgentLogRepository,
)
from .session_state import SessionState

logger = get_logger(LogContexts.AGENT)


class TherapistAgent:
    """
    Main therapist agent for Opora.
    Original logic from Opora agent/main.py preserved exactly.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.llm_client = OpenRouterClient()
        self.evaluator = TherapistEvaluator()

    async def _build_sessions_data(
        self,
        *,
        user_id: int,
        session_repo: SessionRepository,
        msg_repo: MessageRepository,
        exclude_session_id: int | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build evaluator-ready history payload from DB sessions."""
        all_sessions = await session_repo.get_all_account_sessions(user_id)
        sessions_data: dict[str, dict[str, Any]] = {}
        for s in all_sessions:
            if exclude_session_id and s.id == exclude_session_id:
                continue
            session_key = f"session_{s.session_number}"
            messages = await msg_repo.get_session_messages(s.id)
            dialogs = [f"{'PATIENT' if m.role == 'patient' else 'DOCTOR'}: {m.content}" for m in messages]
            sessions_data[session_key] = {
                "therapy": s.therapy_type,
                "dialogs": dialogs,
            }
        return sessions_data

    async def start_new_session(self, state: SessionState) -> Dict[str, Any]:
        """
        Start new therapy session.
        NEW: Uses normalized schema (AccountRepository, ClinicalProfileRepository).
        """
        patient_id = state.patient_id
        account_id_int = int(patient_id)

        # Get or create account with medical info (new schema)
        async with get_db_session() as session:
            account_repo = AccountRepository(session)
            clinical_repo = ClinicalProfileRepository(session)

            account = await account_repo.get_by_id(account_id_int)

            if not account:
                # Create account with default info
                account = await account_repo.create_from_telegram(
                    telegram_id=account_id_int,
                )

            # Build patient record from clinical profile (new schema)
            patient_record = await clinical_repo.get_patient_record(account_id_int)
            if not patient_record:
                patient_record = {
                    "patient pseudonym": "",
                    "patient age": "",
                    "mental health history": "",
                    "physical health history": "",
                    "current problems and symptoms": "",
                }

            session_repo = SessionRepository(session)
            msg_repo = MessageRepository(session)
            sessions_data = await self._build_sessions_data(
                user_id=account.id,
                session_repo=session_repo,
                msg_repo=msg_repo,
                exclude_session_id=state.session_db_id,
            )

        # Cross-session evaluation (async)
        evaluation_result = await self.evaluator.cross_session_evaluate(
            user_id=account_id_int,
            sessions_data=sessions_data,
            patient_record=patient_record,
            session_id=state.session_db_id,
        )

        state.current_therapy = evaluation_result.get("new_therapy", "unspecified therapy")
        state.dialog_count = 0
        state.current_stage = ""

        # Generate personalized greeting based on session number and profile
        # NEW: Include address_mode for proper formal/informal greeting
        if state.session_counter == 1:
            greeting = TherapistPrompts.get_first_session_greeting(
                therapist_name=state.therapist_name,
                patient_display_name=state.patient_display_name,
                language="ru",
                address_mode=state.address_mode,  # NEW
            )
        else:
            greeting = TherapistPrompts.get_return_session_greeting(
                therapist_name=state.therapist_name,
                patient_display_name=state.patient_display_name,
                language="ru",
                address_mode=state.address_mode,  # NEW
            )
        
        # Save therapy reason (async)
        async with get_db_session() as session:
            decision_repo = DecisionLogRepository(session)
            await decision_repo.log_decision(
                session_id=state.session_db_id or 0,
                response_number=0,  # Initial session setup
                current_therapy=state.current_therapy,
                strategy_description=evaluation_result.get("reason", ""),
            )
        
        return {
            'patient_id': patient_id,
            'session_id': state.session_id,
            'therapist_response': greeting,
            'current_therapy': state.current_therapy,
            'reason': evaluation_result.get("reason", ""),
        }
    
    async def process_patient_input(
        self,
        patient_response: Dict[str, Any],
        state: SessionState,
    ) -> Dict[str, Any]:
        """
        Process patient input and generate response.
        Original logic from main.py lines 112-204.
        """
        patient_text = patient_response["text"]
        patient_attitude = patient_response.get("attitude", "neutral")
        
        if not state.session_id:
            return {
                "therapist_response": "There is no active session.",
                "session_ended": False,
                "current_therapy": "unspecified therapy",
                "strategy": {"strategy": "", "strategy_text": ""},
            }
        
        state.dialog_count += 1
        
        user_id_int = int(state.patient_id) if state.patient_id else 0
        
        # Evaluate all conditions (async calls)
        should_end = await self.evaluator.should_end_session(
            patient_text,
            state.dialog_count,
            user_id_int,
            state.session_db_id,
        )
        
        is_rejecting = await self.evaluator.evaluate_client_reaction(
            patient_text,
            user_id_int,
            state.session_db_id,
        )
        
        emotion_result = await self.evaluator.assess_emotion(
            patient_text,
            user_id_int,
            state.session_db_id,
        )
        
        if not isinstance(emotion_result, dict):
            emotion_result = {}
        
        emotion_data = {
            "primary_emotion": emotion_result.get("primary_emotion", ""),
            "emotional_intensity": float(emotion_result.get("emotional_intensity", 0.0)),
        }
        
        # Get memory result - need sessions data from DB
        async with get_db_session() as session:
            session_repo = SessionRepository(session)
            msg_repo = MessageRepository(session)
            
            sessions_data = await self._build_sessions_data(
                user_id=user_id_int,
                session_repo=session_repo,
                msg_repo=msg_repo,
            )
            
            memory_result = await self.evaluator.should_use_memory(
                sessions_data,
                patient_text,
                user_id_int,
                state.session_db_id,
            )
            
            # Get current stage
            current_stage = state.current_stage
            if state.session_db_id:
                current_session = await session_repo.get_by_id(state.session_db_id)
                if current_session and current_session.current_stage:
                    current_stage = current_session.current_stage
                else:
                    # Determine stage using evaluator
                    current_stage = await self.evaluator.determine_treatment_stage(
                        sessions_data,
                        state.current_therapy,
                        user_id_int,
                        state.session_db_id,
                    )
                    # Save stage if we have a current session
                    if state.session_db_id:
                        await session_repo.update_current_stage(
                            state.session_db_id,
                            current_stage,
                        )
                state.current_stage = current_stage
        
        # Get response strategy
        strategy_result = await self.evaluator.update_response_strategy(
            emotion_data=emotion_data,
            is_rejecting=is_rejecting,
            patient_input=patient_text,
            patient_id=state.patient_id,
            user_id=user_id_int,
            session_id=state.session_db_id,
        )
        
        strategy = {
            "strategy": strategy_result.get("strategy", ""),
            "strategy_text": strategy_result.get("strategy_text", ""),
        }
        
        # Generate response
        response = await self._generate_response(
            patient_input=patient_text,
            emotion_data=emotion_data,
            current_therapy=state.current_therapy,
            current_stage=current_stage,
            strategy=strategy,
            memory_result=memory_result,
            user_id=user_id_int,
            state=state,
        )
        
        # Log decision data
        decision_data = {
            "Memory Invoke": memory_result,
            "Whether to Reject or Deviate": is_rejecting,
            "Current Therapy": state.current_therapy,
            "Current Stage": current_stage,
            "Primary Emotion": emotion_result.get("primary_emotion", ""),
            "Emotional Intensity": emotion_result.get("emotional_intensity", 0.0),
            "Response Strategy": strategy_result.get("strategy", ""),
            "Strategy Description": strategy_result.get("strategy_text", ""),
            "Attitude": patient_attitude,
        }
        
        async with get_db_session() as session:
            decision_repo = DecisionLogRepository(session)
            await decision_repo.log_decision(
                session_id=state.session_db_id or 0,
                response_number=state.dialog_count,
                memory_invoke_result=memory_result,
                is_rejecting=is_rejecting,
                current_therapy=state.current_therapy,
                current_stage=current_stage,
                primary_emotion=emotion_result.get("primary_emotion"),
                emotional_intensity=emotion_result.get("emotional_intensity"),
                response_strategy=strategy_result.get("strategy"),
                strategy_description=strategy_result.get("strategy_text"),
                patient_attitude=patient_attitude,
                decision_snapshot=decision_data,
            )
        
        return {
            "therapist_response": response,
            "session_ended": should_end,
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
        """
        Generate therapist response.
        Original logic from main.py lines 215-289.
        """
        # Get session memory for context
        session_memory = {"dialogs": []}
        if state.session_id and state.session_db_id:
            async with get_db_session() as session:
                msg_repo = MessageRepository(session)
                try:
                    messages = await msg_repo.get_latest_messages(
                        state.session_db_id,
                        count=10,
                    )
                    dialogs = [f"{'PATIENT' if m.role == 'patient' else 'DOCTOR'}: {m.content}" for m in messages]
                    session_memory = {"dialogs": dialogs}
                except Exception:
                    pass
        
        primary_emotion = emotion_data.get("primary_emotion", "unknown")
        emotional_intensity = emotion_data.get("emotional_intensity", 0.0)
        current_strategy = strategy.get("strategy", "")
        current_strategy_text = strategy.get("strategy_text", "")
        
        # Build personalized system message and prompt
        # NEW: Include address_mode and styles in system message and prompt
        system_message = TherapistPrompts.get_system_message(
            therapist_name=state.therapist_name,
            therapist_gender=state.therapist_gender,
            therapist_styles=state.therapist_styles,  # NEW: styles instead of traits
            address_mode=state.address_mode,  # NEW
        )

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
            patient_sex=state.patient_sex,  # NEW
            therapist_styles=state.therapist_styles,  # NEW: styles instead of traits
            address_mode=state.address_mode,  # NEW
        )

        result = await self.llm_client.chat_completion(
            model=self.settings.llm_therapist_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            temperature=self.settings.llm_therapist_temperature,
            max_tokens=self.settings.llm_therapist_max_tokens,
            task_name="generate_response",
        )

        async with get_db_session() as session:
            agent_log_repo = AgentLogRepository(session)
            await agent_log_repo.log_llm_call(
                account_id=user_id,
                agent_type="therapist",
                task_name="generate_response",
                model=self.settings.llm_therapist_model,
                temperature=self.settings.llm_therapist_temperature,
                max_tokens=self.settings.llm_therapist_max_tokens,
                prompt=prompt[:5000],
                response=result["content"][:5000] if result["content"] else None,
                latency_ms=result["latency_ms"],
                tokens_input=result["usage"]["prompt_tokens"],
                tokens_output=result["usage"]["completion_tokens"],
                success=result["success"],
                error_message=result["error"],
                session_id=state.session_db_id,
            )

        if result["success"]:
            raw_response = result["content"]
            clean_response = raw_response.replace('\\"', '"')
            clean_response = clean_response.strip('"')
            return clean_response

        # Return Russian fallback adapted to address_mode
        return TherapistPrompts.get_fallback_response(
            language="ru",
            address_mode=state.address_mode,  # NEW
        )
