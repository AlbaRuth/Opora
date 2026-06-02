"""LLM-based meaning analysis for patient dialogue signals."""

from __future__ import annotations

from typing import Any

from agents.evaluators.structured_outputs import DialogueSignalResult, validate_model
from services.llm import LlmGateway


class DialogueSignalAnalyzer:
    """Analyze patient intent and emotional signals without code keyword rules."""

    SYSTEM_PROMPT = """Role:
You are a clinical dialogue signal analyst for a psychological counseling product.

Task:
Analyze the patient's current message in context and return one JSON object. Evaluate meaning,
not surface phrases. Do not rely on examples as exact triggers.

Context:
You receive the current patient message, recent dialogue, selected counselor styles, intake card
gaps, current phase, and turn counts.

Clinical boundaries:
- Treat crisis or self-harm risk conservatively when meaning is uncertain.
- Distinguish ordinary frustration from a firm request to stop questions.
- Distinguish advice seeking from a request to understand feelings.
- Choose an active style only from the available styles when possible.

Decision criteria:
- crisis_signal: true when the patient expresses imminent or serious danger, self-harm intent,
  inability to stay safe, or similarly urgent risk.
- pushback_type: "stage" when the patient resists intake pacing, asks to skip questions, or asks
  for advice before enough context; "hard_stop" when they clearly refuse more questions now.
- session_end_intent: true only when the patient clearly intends to end the conversation now.
- question_guidance: "defer" for crisis, hard stop, or strong stage pushback; otherwise
  "encourage" when intake card gaps remain; otherwise "optional".
- recommended_response_mode: choose hold_space, gentle_explore, or structured_gather.

Output schema:
{
  "primary_emotion": "string",
  "emotional_intensity": 0.0,
  "crisis_signal": false,
  "pushback_type": "none",
  "advice_request": false,
  "question_stop": false,
  "session_end_intent": false,
  "active_style": "friendly",
  "recommended_response_mode": "gentle_explore",
  "question_guidance": "encourage",
  "confidence": 0.0,
  "rationale_short": "string"
}

Failure behavior:
Return JSON only. If uncertain, choose the safer clinical option and lower confidence."""

    @staticmethod
    def build_user_prompt(
        *,
        patient_message: str,
        recent_dialogue: list[dict[str, str]] | None = None,
        therapist_styles: list[str] | None = None,
        current_phase: str = "therapy",
        current_user_turns: int = 0,
        missing_fields: list[str] | None = None,
        max_user_turns: int | None = None,
    ) -> str:
        return f"""Analyze this dialogue turn.

Current phase: {current_phase}
Current patient message:
{patient_message}

Recent dialogue:
{recent_dialogue or []}

Available counselor styles:
{therapist_styles or []}

Missing intake fields:
{missing_fields or []}

Current user turns in phase: {current_user_turns}
Max user turns in phase: {max_user_turns}

Return JSON only."""

    def __init__(self, llm_gateway: LlmGateway | None = None) -> None:
        self.llm_gateway = llm_gateway or LlmGateway()

    async def analyze(
        self,
        *,
        patient_message: str,
        account_id: int,
        session_id: int | None = None,
        recent_dialogue: list[dict[str, str]] | None = None,
        therapist_styles: list[str] | None = None,
        current_phase: str = "therapy",
        current_user_turns: int = 0,
        missing_fields: list[str] | None = None,
        max_user_turns: int | None = None,
    ) -> DialogueSignalResult:
        user_prompt = self.build_user_prompt(
            patient_message=patient_message,
            recent_dialogue=recent_dialogue,
            therapist_styles=therapist_styles,
            current_phase=current_phase,
            current_user_turns=current_user_turns,
            missing_fields=missing_fields,
            max_user_turns=max_user_turns,
        )
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        result = await self.llm_gateway.complete(
            agent_type="evaluator",
            task_name="dialogue_signal_analysis",
            messages=messages,
            account_id=account_id,
            session_id=session_id,
            prompt=user_prompt,
            prompt_template="DialogueSignalAnalyzer.build_user_prompt",
            prompt_variables={
                "patient_message": patient_message,
                "recent_dialogue": recent_dialogue or [],
                "therapist_styles": therapist_styles or [],
                "current_phase": current_phase,
                "current_user_turns": current_user_turns,
                "missing_fields": missing_fields or [],
                "max_user_turns": max_user_turns,
            },
            metadata={"flow_phase": current_phase},
        )
        if result.get("success"):
            validated = validate_model(DialogueSignalResult, result.get("content"))
            if isinstance(validated, DialogueSignalResult):
                return validated
        return DialogueSignalResult()
