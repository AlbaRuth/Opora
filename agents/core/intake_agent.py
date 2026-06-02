"""
Intake agent for initial clinical card collection.
NEW: Uses normalized schema (ClinicalProfileRepository), includes address_mode, context window,
and anti-repetition logic for more natural dialogue.
"""

from __future__ import annotations

import json
from typing import Any

from core.config import get_settings
from core.logging import LogContexts, get_logger
from db.repositories import AgentLogRepository, ClinicalProfileRepository, MessageRepository
from db.session import get_db_session
from integrations.langfuse import get_current_trace_id
from integrations.openrouter import OpenRouterClient

from agents.evaluators.therapist_evaluator import TherapistEvaluator
from agents.intake.response_policy import IntakeResponsePolicy
from agents.prompts.intake_prompts import IntakePrompts

from .session_state import SessionState

logger = get_logger(LogContexts.AGENT)


class IntakeAgent:
    """Collects intake information and updates patient card."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_client = OpenRouterClient()
        self.evaluator = TherapistEvaluator()

    def _compute_max_user_turns(self) -> int | None:
        """Compute maximum user turns for intake based on settings."""
        return self.settings.intake_max_user_turns

    def _get_context_window_size(self) -> int:
        """Get the size of the dialogue context window."""
        multiplier = getattr(self.settings, 'intake_context_window_multiplier', 2)
        return self.settings.intake_min_user_turns * multiplier

    async def _get_recent_dialogue(
        self,
        session_id: int,
        limit: int,
    ) -> list[dict[str, str]]:
        """Get recent dialogue messages for context window."""
        async with get_db_session() as session:
            message_repo = MessageRepository(session)
            messages = await message_repo.get_recent_messages(session_id, limit=limit)
            return [
                {"role": "user" if msg.role == "patient" else "assistant", "content": msg.content}
                for msg in messages
            ]

    async def process_patient_input(
        self,
        patient_text: str,
        state: SessionState,
    ) -> dict[str, Any]:
        """Process one intake turn and return next intake response."""
        account_id = int(state.patient_id)
        trace_id = get_current_trace_id()
        max_user_turns = self._compute_max_user_turns()

        async with get_db_session() as session:
            clinical_repo = ClinicalProfileRepository(session)

            # Get current clinical card
            current_card = await clinical_repo.get_patient_record(account_id)
            if not current_card:
                # Fallback if no clinical profile exists
                return {
                    "therapist_response": IntakePrompts.get_fallback_intake_response(
                        state.patient_display_name,
                        state.address_mode,
                        state.therapist_gender,
                        patient_text,
                    ),
                    "intake_completed": False,
                    "missing_fields": self.settings.intake_required_fields_list,
                    "card_updates": {},
                    "strategy": {},
                }

            # Get recent dialogue for context window
            context_window_size = self._get_context_window_size()
            recent_dialogue = []
            if state.session_db_id:
                recent_dialogue = await self._get_recent_dialogue(
                    state.session_db_id,
                    limit=context_window_size,
                )

            primary_emotion = ""
            emotional_intensity = 0.0
            if self.settings.intake_emotion_eval_enabled:
                emotion_result = await self.evaluator.assess_emotion(
                    patient_text,
                    account_id,
                    state.session_db_id,
                )
                if isinstance(emotion_result, dict):
                    primary_emotion = str(emotion_result.get("primary_emotion", "") or "")
                    try:
                        emotional_intensity = float(
                            emotion_result.get("emotional_intensity", 0.0) or 0.0
                        )
                    except (TypeError, ValueError):
                        emotional_intensity = 0.0

            missing_before = self._missing_required_fields(current_card)
            turn_directives = IntakeResponsePolicy.compute_directives(
                patient_message=patient_text,
                therapist_styles=state.therapist_styles,
                current_user_turns=state.intake_user_turns,
                primary_emotion=primary_emotion,
                emotional_intensity=emotional_intensity,
                missing_fields=missing_before,
                recent_dialogue=recent_dialogue,
                min_sentences=self.settings.intake_min_response_sentences,
                max_question_words=self.settings.intake_max_question_words,
                hold_emotion_intensity_threshold=(
                    self.settings.intake_hold_emotion_intensity_threshold
                ),
                max_user_turns=max_user_turns,
            )

            system_prompt = IntakePrompts.get_system_message(
                therapist_name=state.therapist_name,
                therapist_gender=state.therapist_gender,
                therapist_styles=state.therapist_styles,
                patient_name=state.patient_display_name,
                patient_age=state.patient_age,
                patient_sex=state.patient_sex,
                address_mode=state.address_mode,
                min_user_turns=self.settings.intake_min_user_turns,
                required_fields=self.settings.intake_required_fields_list,
                max_user_turns=max_user_turns,
            )
            user_prompt = IntakePrompts.get_intake_turn_user_prompt(
                patient_message=patient_text,
                current_card=current_card,
                current_user_turns=state.intake_user_turns,
                recent_dialogue=recent_dialogue,
                therapist_styles=state.therapist_styles,
                therapist_name=state.therapist_name,
                max_user_turns=max_user_turns,
                turn_directives=turn_directives,
                missing_fields=missing_before,
                required_fields=self.settings.intake_required_fields_list,
            )

            intake_strategy = {
                "primary_emotion": primary_emotion,
                "emotional_intensity": emotional_intensity,
                "response_mode": turn_directives.response_mode,
                "question_guidance": turn_directives.question_guidance,
                "allow_question": turn_directives.allow_question,
                "pushback_type": turn_directives.pushback_type,
                "active_style": turn_directives.active_style,
                "missing_fields_count": len(missing_before),
                "suggested_focus_field": turn_directives.suggested_focus_field,
            }

            result = await self.llm_client.chat_completion(
                model=self.settings.llm_intake_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.settings.llm_intake_temperature,
                max_tokens=self.settings.llm_intake_max_tokens,
                task_name="intake_turn",
                top_p=getattr(self.settings, 'llm_intake_top_p', None),
                frequency_penalty=getattr(self.settings, 'llm_intake_frequency_penalty', None),
                presence_penalty=getattr(self.settings, 'llm_intake_presence_penalty', None),
            )

            parsed = self._parse_json_content(result["content"]) if result["success"] else {}
            merged = self._merge_card(current_card, parsed)
            missing_required = self._missing_required_fields(merged)
            user_turns_after_processing = state.intake_user_turns + 1

            # Check for completion: either normal completion OR max turns reached
            reached_max_turns = max_user_turns and user_turns_after_processing >= max_user_turns
            is_complete = (
                (bool(parsed.get("is_intake_complete", False))
                 and user_turns_after_processing >= self.settings.intake_min_user_turns
                 and not missing_required)
                or reached_max_turns
            )

            # Flag for insufficient initial information if max turns reached with missing fields
            initial_info_insufficient = False
            if reached_max_turns and missing_required:
                initial_info_insufficient = True
                # Prepend warning to hypothesis explanation
                insufficient_note = (
                    "Первоначально было дано недостаточно информации для полноценного первичного профиля; "
                    "выводы предварительны и ограничены доступными данными. "
                )
                merged["intake_hypothesis_explanation"] = insufficient_note + merged.get("intake_hypothesis_explanation", "")

            # Update clinical profile using new repository
            await clinical_repo.update_clinical_data(
                account_id=account_id,
                mental_health_history=merged["mental_health_history"],
                physical_health_history=merged["physical_health_history"],
                current_problems=merged["current_problems"],
                intake_hypothesis=merged["intake_hypothesis"],
                intake_hypothesis_explanation=merged["intake_hypothesis_explanation"],
                initial_info_insufficient=initial_info_insufficient,
            )

            await self._log_call(
                account_id=account_id,
                session_id=state.session_db_id,
                prompt=user_prompt,
                result=result,
                trace_id=trace_id,
                metadata={
                    "flow_phase": "intake",
                    "intake_user_turns_before": state.intake_user_turns,
                    "intake_user_turns_after": user_turns_after_processing,
                    "missing_required_fields": missing_required,
                    "is_intake_complete": is_complete,
                    "initial_info_insufficient": initial_info_insufficient,
                    "patient_sex": state.patient_sex,
                    "address_mode": state.address_mode,
                    "primary_emotion": primary_emotion,
                    "emotional_intensity": emotional_intensity,
                    "response_mode": turn_directives.response_mode,
                    "question_guidance": turn_directives.question_guidance,
                    "allow_question": turn_directives.allow_question,
                    "pushback_type": turn_directives.pushback_type,
                    "suggested_focus_field": turn_directives.suggested_focus_field,
                    "missing_fields_count": len(missing_before),
                },
            )

            response_text = self._safe_text(parsed.get("patient_response_ru"))
            if not response_text:
                response_text = IntakePrompts.get_fallback_intake_response(
                    state.patient_display_name,
                    state.address_mode,
                    state.therapist_gender,
                    patient_text,
                )

            return {
                "therapist_response": response_text,
                "intake_completed": is_complete,
                "missing_fields": missing_required,
                "initial_info_insufficient": initial_info_insufficient,
                "card_updates": merged,
                "strategy": intake_strategy,
            }

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
        try:
            data = json.loads(cleaned)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            logger.warning("intake_json_parse_failed")
            return {}

    def _merge_card(self, current_card: dict[str, str], parsed: dict[str, Any]) -> dict[str, str]:
        return {
            "mental_health_history": self._safe_text(parsed.get("mental_health_history"))
            or current_card.get("mental_health_history", ""),
            "physical_health_history": self._safe_text(parsed.get("physical_health_history"))
            or current_card.get("physical_health_history", ""),
            "current_problems": self._safe_text(parsed.get("current_problems"))
            or current_card.get("current_problems", ""),
            "intake_hypothesis": self._safe_text(parsed.get("intake_hypothesis"))
            or current_card.get("intake_hypothesis", ""),
            "intake_hypothesis_explanation": self._safe_text(parsed.get("intake_hypothesis_explanation"))
            or current_card.get("intake_hypothesis_explanation", ""),
        }

    def _missing_required_fields(self, merged_card: dict[str, str]) -> list[str]:
        return [
            field
            for field in self.settings.intake_required_fields_list
            if not merged_card.get(field, "").strip()
        ]

    def _safe_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    async def _log_call(
        self,
        account_id: int,
        session_id: int | None,
        prompt: str,
        result: dict[str, Any],
        trace_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        async with get_db_session() as session:
            agent_log_repo = AgentLogRepository(session)
            await agent_log_repo.log_llm_call(
                account_id=account_id,
                session_id=session_id,
                agent_type="intake",
                task_name="intake_turn",
                model=self.settings.llm_intake_model,
                temperature=self.settings.llm_intake_temperature,
                max_tokens=self.settings.llm_intake_max_tokens,
                prompt=prompt[:5000],
                response=result.get("content", "")[:5000],
                latency_ms=result.get("latency_ms"),
                tokens_input=result.get("usage", {}).get("prompt_tokens", 0),
                tokens_output=result.get("usage", {}).get("completion_tokens", 0),
                success=result.get("success", False),
                error_message=result.get("error"),
                langfuse_trace_id=trace_id,
                metadata=metadata,
            )
