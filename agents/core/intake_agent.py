"""
Intake agent for initial clinical card collection.
"""

from __future__ import annotations

import json
from typing import Any

from core.config import get_settings
from core.logging import LogContexts, get_logger
from db.repositories import AgentLogRepository, UserRepository
from db.session import get_db_session
from integrations.langfuse import get_current_trace_id
from integrations.openrouter import OpenRouterClient

from .session_state import SessionState
from agents.prompts.intake_prompts import IntakePrompts

logger = get_logger(LogContexts.AGENT)


class IntakeAgent:
    """Collects intake information and updates patient card."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_client = OpenRouterClient()

    async def process_patient_input(
        self,
        patient_text: str,
        state: SessionState,
    ) -> dict[str, Any]:
        """Process one intake turn and return next intake response."""
        user_id = int(state.patient_id)
        trace_id = get_current_trace_id()

        async with get_db_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_id(user_id)
            if not user:
                return {
                    "therapist_response": IntakePrompts.get_fallback_intake_response(state.patient_display_name),
                    "intake_completed": False,
                    "missing_fields": self.settings.intake_required_fields_list,
                    "card_updates": {},
                }

            current_card = user.get_patient_record()
            prompt = IntakePrompts.get_intake_turn_prompt(
                patient_message=patient_text,
                patient_name=state.patient_display_name,
                patient_age=state.patient_age,
                current_card=current_card,
                min_user_turns=self.settings.intake_min_user_turns,
                current_user_turns=state.intake_user_turns,
                required_fields=self.settings.intake_required_fields_list,
                max_question_words=self.settings.intake_max_question_words,
                summary_max_words=self.settings.intake_summary_max_words,
            )

            result = await self.llm_client.chat_completion(
                model=self.settings.llm_intake_model,
                messages=[
                    {"role": "system", "content": IntakePrompts.get_system_message()},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.settings.llm_intake_temperature,
                max_tokens=self.settings.llm_intake_max_tokens,
                task_name="intake_turn",
            )

            parsed = self._parse_json_content(result["content"]) if result["success"] else {}
            merged = self._merge_card(current_card, parsed)
            missing_required = self._missing_required_fields(merged)
            user_turns_after_processing = state.intake_user_turns + 1
            is_complete = (
                bool(parsed.get("is_intake_complete", False))
                and user_turns_after_processing >= self.settings.intake_min_user_turns
                and not missing_required
            )

            await user_repo.update_patient_card(
                user_id=user_id,
                mental_health=merged["mental_health_history"],
                physical_health=merged["physical_health_history"],
                problems=merged["current_problems"],
                intake_hypothesis=merged["intake_hypothesis"],
                intake_hypothesis_explanation=merged["intake_hypothesis_explanation"],
            )

            await self._log_call(
                user_id=user_id,
                session_id=state.session_db_id,
                prompt=prompt,
                result=result,
                trace_id=trace_id,
                metadata={
                    "flow_phase": "intake",
                    "intake_user_turns_before": state.intake_user_turns,
                    "intake_user_turns_after": user_turns_after_processing,
                    "missing_required_fields": missing_required,
                    "is_intake_complete": is_complete,
                },
            )

            response_text = self._safe_text(parsed.get("patient_response_ru"))
            if not response_text:
                response_text = IntakePrompts.get_fallback_intake_response(state.patient_display_name)

            return {
                "therapist_response": response_text,
                "intake_completed": is_complete,
                "missing_fields": missing_required,
                "card_updates": merged,
            }

    async def update_card_from_message(
        self,
        patient_text: str,
        state: SessionState,
    ) -> dict[str, str]:
        """Background card update during therapy stage without user confirmation."""
        user_id = int(state.patient_id)
        trace_id = get_current_trace_id()

        async with get_db_session() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_id(user_id)
            if not user:
                return {}

            current_card = user.get_patient_record()
            prompt = IntakePrompts.get_background_update_prompt(
                patient_message=patient_text,
                current_card=current_card,
            )
            result = await self.llm_client.chat_completion(
                model=self.settings.llm_intake_model,
                messages=[
                    {"role": "system", "content": IntakePrompts.get_system_message()},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.settings.llm_intake_temperature,
                max_tokens=self.settings.llm_intake_max_tokens,
                task_name="intake_background_update",
            )
            parsed = self._parse_json_content(result["content"]) if result["success"] else {}
            updates = {
                "mental_health_history": self._safe_text(parsed.get("mental_health_history")),
                "physical_health_history": self._safe_text(parsed.get("physical_health_history")),
                "current_problems": self._safe_text(parsed.get("current_problems")),
                "intake_hypothesis": self._safe_text(parsed.get("intake_hypothesis")),
                "intake_hypothesis_explanation": self._safe_text(parsed.get("intake_hypothesis_explanation")),
            }
            normalized_updates = {k: v for k, v in updates.items() if v}
            if normalized_updates:
                await user_repo.update_patient_card(
                    user_id=user_id,
                    mental_health=normalized_updates.get("mental_health_history"),
                    physical_health=normalized_updates.get("physical_health_history"),
                    problems=normalized_updates.get("current_problems"),
                    intake_hypothesis=normalized_updates.get("intake_hypothesis"),
                    intake_hypothesis_explanation=normalized_updates.get("intake_hypothesis_explanation"),
                )

            await self._log_call(
                user_id=user_id,
                session_id=state.session_db_id,
                prompt=prompt,
                result=result,
                trace_id=trace_id,
                metadata={
                    "flow_phase": "therapy",
                    "background_update": True,
                    "updated_fields": sorted(normalized_updates.keys()),
                },
            )
            return normalized_updates

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
        user_id: int,
        session_id: int | None,
        prompt: str,
        result: dict[str, Any],
        trace_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        async with get_db_session() as session:
            agent_log_repo = AgentLogRepository(session)
            await agent_log_repo.log_llm_call(
                user_id=user_id,
                session_id=session_id,
                agent_type="intake",
                task_name=metadata.get("background_update") and "intake_background_update" or "intake_turn",
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
