"""Therapist evaluator tasks and structured response parsing."""

import json
from typing import Any, Dict

from core.config import get_settings
from core.logging import get_logger, LogContexts
from agents.prompts.evaluator_prompts import EvaluatorPrompts
from agents.evaluators.structured_outputs import (
    EmotionAssessmentResult,
    ResponseStrategyResult,
    TherapyProgressResult,
    extract_json_object,
    validate_model,
)
from db.session import get_db_session
from db.repositories import SessionRepository, MessageRepository, DecisionLogRepository
from services.llm import LlmGateway

logger = get_logger(LogContexts.AGENT)


class TherapistEvaluator:
    """
    Evaluates therapy sessions and patient responses.
    Original logic from Opora agent/evaluation.py preserved.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.llm_gateway = LlmGateway()
    
    def _parse_response(self, response: Any) -> Any:
        """Parse LLM response without regex cleanup."""
        if isinstance(response, str):
            parsed = extract_json_object(response)
            return parsed if parsed else response.strip()
        return response
    
    async def _call_llm(
        self,
        prompt: str,
        task_name: str,
    ) -> dict[str, Any]:
        """Call LLM with logging."""
        return await self.llm_gateway.complete(
            agent_type="evaluator",
            task_name=task_name,
            messages=[
                {"role": "system", "content": EvaluatorPrompts.EVALUATOR_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            prompt=prompt,
            prompt_template=f"EvaluatorPrompts.{task_name}",
            prompt_variables={"rendered_prompt": prompt},
            log=False,
        )
    
    async def _log_agent_call(
        self,
        user_id: int,
        task_name: str,
        prompt: str,
        result: dict[str, Any],
        session_id: int | None = None,
    ) -> None:
        """Log agent call to database."""
        try:
            await self.llm_gateway.log_result(
                account_id=user_id,
                session_id=session_id,
                agent_type="evaluator",
                task_name=task_name,
                messages=[
                    {"role": "system", "content": EvaluatorPrompts.EVALUATOR_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                prompt=prompt,
                prompt_template=f"EvaluatorPrompts.{task_name}",
                prompt_variables={"rendered_prompt": prompt},
                metadata={},
                result=result,
            )
        except Exception as e:
            logger.warning("failed_to_log_agent_call", error=str(e))
    
    async def assess_emotion(
        self,
        patient_input: str,
        user_id: int,
        session_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        Assess primary emotion and intensity.
        Original logic from evaluation.py lines 183-205.
        """
        prompt = EvaluatorPrompts.EMOTION_ASSESSMENT.format(patient_input=patient_input)
        
        response_result = await self._call_llm(
            prompt=prompt,
            task_name="assess_emotion",
        )
        response = response_result.get("content", "")
        
        await self._log_agent_call(
            user_id=user_id,
            task_name="assess_emotion",
            prompt=prompt,
            result=response_result,
            session_id=session_id,
        )
        
        try:
            parsed = validate_model(EmotionAssessmentResult, response)
            result = parsed if isinstance(parsed, EmotionAssessmentResult) else None
            return {
                "primary_emotion": result.primary_emotion if result else "",
                "emotional_intensity": result.emotional_intensity if result else 0.0,
            }
        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            logger.warning("failed_to_parse_emotion", error=str(e), response=response)
            return {
                "primary_emotion": "",
                "emotional_intensity": 0.0,
            }
    
    async def update_response_strategy(
        self,
        emotion_data: Dict[str, Any],
        is_rejecting: bool,
        patient_input: str,
        patient_id: str,
        user_id: int,
        session_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        Update response strategy based on emotion and rejection.
        Original logic from evaluation.py lines 207-262.
        """
        # Get strategy memory for this session
        session_strategy_memory = await self._get_session_strategy_memory(session_id)
        
        primary_emotion = emotion_data.get('primary_emotion', 'unknown')
        emotional_intensity = f"{emotion_data.get('emotional_intensity', 0.0):.1f}"
        
        prompt = EvaluatorPrompts.get_strategy_prompt(
            patient_input=patient_input,
            primary_emotion=primary_emotion,
            emotional_intensity=float(emotional_intensity),
            is_rejecting=is_rejecting,
            session_strategy_memory=session_strategy_memory,
        )
        
        response_result = await self._call_llm(
            prompt=prompt,
            task_name="update_response_strategy",
        )
        response = response_result.get("content", "")
        
        await self._log_agent_call(
            user_id=user_id,
            task_name="update_response_strategy",
            prompt=prompt,
            result=response_result,
            session_id=session_id,
        )
        
        try:
            parsed = validate_model(ResponseStrategyResult, response)
            result = parsed if isinstance(parsed, ResponseStrategyResult) else None
            return {
                "strategy": result.strategy if result else "",
                "strategy_text": result.strategy_text if result else "",
            }
        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            logger.warning("failed_to_parse_strategy", error=str(e), response=response)
            return {
                "strategy": "",
                "strategy_text": "",
            }
    
    async def _get_session_strategy_memory(
        self,
        session_id: int | None,
    ) -> str:
        """Get list of strategies used in current session."""
        if not session_id:
            return "No strategy memory available"
        
        try:
            async with get_db_session() as db_session:
                repo = DecisionLogRepository(db_session)
                strategies = await repo.get_strategies_used_in_session(session_id)
                
                if not strategies:
                    return "No strategy memory available"
                
                return f"Strategies used in this session: {', '.join(strategies)}"
        except Exception:
            return "No strategy memory available"
    
    async def should_use_memory(
        self,
        all_sessions_memory: Dict[str, Dict],
        patient_input: str,
        user_id: int,
        session_id: int | None = None,
    ) -> str:
        """
        Determine if historical memory should be used.
        Original logic from evaluation.py lines 335-357.
        """
        all_dialogs = []
        for session in all_sessions_memory.values():
            all_dialogs.extend(session.get("dialogs", []))
        
        prompt = EvaluatorPrompts.MEMORY_USAGE.format(
            all_dialogs=all_dialogs,
            patient_input=patient_input,
        )
        
        response_result = await self._call_llm(
            prompt=prompt,
            task_name="should_use_memory",
        )
        response = response_result.get("content", "")
        
        await self._log_agent_call(
            user_id=user_id,
            task_name="should_use_memory",
            prompt=prompt,
            result=response_result,
            session_id=session_id,
        )
        
        return response if response else "No need to consider historical conversation memory"
    
    async def should_end_farewell_intent(
        self,
        patient_input: str,
        dialog_count: int,
        user_id: int,
        session_id: int | None = None,
    ) -> bool:
        """Deprecated: sessions are not closed automatically from dialogue content."""
        _ = (patient_input, dialog_count, user_id, session_id)
        return False
    
    async def evaluate_therapy_progress(
        self,
        last_session_memory: Dict,
        user_id: int,
        session_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        Evaluate therapy progress and suggest new therapy.
        Original logic from evaluation.py lines 265-294.
        """
        full_dialogs = last_session_memory.get("dialogs", [])
        last_therapy = last_session_memory.get("therapy", "")
        last_dialogs_str = '\n'.join(full_dialogs)
        
        prompt = EvaluatorPrompts.THERAPY_PROGRESS.format(
            last_therapy=last_therapy,
            last_dialogs=last_dialogs_str,
        )
        
        response_result = await self._call_llm(
            prompt=prompt,
            task_name="evaluate_therapy_progress",
        )
        response = response_result.get("content", "")
        
        await self._log_agent_call(
            user_id=user_id,
            task_name="evaluate_therapy_progress",
            prompt=prompt,
            result=response_result,
            session_id=session_id,
        )
        
        try:
            parsed = validate_model(TherapyProgressResult, response)
            result = parsed if isinstance(parsed, TherapyProgressResult) else None
            return {
                "new_therapy": result.new_therapy if result else "cognitive-behavioral therapy",
                "reason": result.reason if result else "maintain the original therapy",
            }
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("failed_to_parse_therapy_progress", error=str(e))
            return {
                "new_therapy": "cognitive-behavioral therapy",
                "reason": "maintain the original therapy",
            }
    
    async def determine_treatment_stage(
        self,
        all_sessions_memory: Dict[str, Dict],
        current_therapy: str,
        user_id: int,
        session_id: int | None = None,
    ) -> str:
        """
        Determine current treatment stage.
        Original logic from evaluation.py lines 296-316.
        """
        all_dialogs = []
        for session in all_sessions_memory.values():
            all_dialogs.extend(session.get("dialogs", []))
        
        prompt = EvaluatorPrompts.TREATMENT_STAGE.format(
            current_therapy=current_therapy,
            all_dialogs=all_dialogs,
        )
        
        response_result = await self._call_llm(
            prompt=prompt,
            task_name="determine_treatment_stage",
        )
        response = response_result.get("content", "")
        
        await self._log_agent_call(
            user_id=user_id,
            task_name="determine_treatment_stage",
            prompt=prompt,
            result=response_result,
            session_id=session_id,
        )
        
        return response if response else "Cannot determine the current treatment stage"
    
    async def select_initial_therapy(
        self,
        patient_record: Dict,
        user_id: int,
        session_id: int | None = None,
    ) -> str:
        """
        Select initial therapy based on patient record.
        Original logic from evaluation.py lines 320-333.
        """
        import json
        medical_record = json.dumps(patient_record, ensure_ascii=False, indent=2)
        
        prompt = EvaluatorPrompts.INITIAL_THERAPY.format(medical_record=medical_record)
        
        response_result = await self._call_llm(
            prompt=prompt,
            task_name="select_initial_therapy",
        )
        response = response_result.get("content", "")
        
        await self._log_agent_call(
            user_id=user_id,
            task_name="select_initial_therapy",
            prompt=prompt,
            result=response_result,
            session_id=session_id,
        )
        
        return response.rstrip('。.') if response else "cognitive-behavioral therapy"
    
    async def cross_session_evaluate(
        self,
        user_id: int,
        sessions_data: Dict[str, Dict],
        patient_record: Dict,
        session_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        Cross-session evaluation to determine therapy.
        Original logic from evaluation.py lines 106-133.
        """
        if not sessions_data:
            # First session
            initial_therapy = await self.select_initial_therapy(
                patient_record, user_id, session_id
            )
            return {
                "new_therapy": initial_therapy,
                "reason": "This is the first conversation, the initial therapy is selected based on the patient's medical record.",
            }
        
        # Get last session
        last_session_num = len(sessions_data)
        last_session = sessions_data.get(f"session_{last_session_num}", {})
        
        evaluation = await self.evaluate_therapy_progress(
            last_session, user_id, session_id
        )
        
        return {
            "new_therapy": evaluation.get("new_therapy", "cognitive-behavioral therapy"),
            "reason": evaluation.get("reason", "maintain the original therapy"),
        }
