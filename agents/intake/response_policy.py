"""Turn-level response directives for IntakeAgent.

This module does not inspect patient text. Meaning-level interpretation is produced by
DialogueSignalAnalyzer and this policy only maps structured signals to prompt directives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agents.evaluators.structured_outputs import DialogueSignalResult

ResponseMode = Literal["hold_space", "gentle_explore", "structured_gather"]
QuestionGuidance = Literal["encourage", "optional", "defer"]
PushbackType = Literal["none", "stage", "hard_stop"]


@dataclass(frozen=True)
class TurnDirectives:
    """Per-turn instructions injected into the intake user prompt."""

    response_mode: ResponseMode
    active_style: str
    min_sentences: int
    max_question_words: int
    allow_question: bool
    question_guidance: QuestionGuidance
    directive_en: str
    pushback_type: PushbackType = "none"
    primary_emotion: str = ""
    emotional_intensity: float = 0.0
    suggested_focus_field: str | None = None
    advice_request: bool = False
    crisis_signal: bool = False
    confidence: float = 0.0
    rationale_short: str = ""


class IntakeResponsePolicy:
    """Computes intake turn directives from structured LLM signal analysis."""

    @staticmethod
    def _resolve_style(
        signal: DialogueSignalResult,
        therapist_styles: list[str] | None,
    ) -> str:
        styles = therapist_styles or []
        if not styles:
            return signal.active_style or "friendly"
        return signal.active_style if signal.active_style in styles else styles[0]

    @staticmethod
    def _resolve_guidance(
        signal: DialogueSignalResult,
        has_gaps: bool,
    ) -> QuestionGuidance:
        if signal.crisis_signal or signal.question_stop or signal.pushback_type != "none":
            return "defer"
        if signal.question_guidance in ("encourage", "optional", "defer"):
            if signal.question_guidance == "optional" and has_gaps:
                return "encourage"
            return signal.question_guidance
        return "encourage" if has_gaps else "optional"

    @staticmethod
    def _resolve_mode(
        signal: DialogueSignalResult,
        guidance: QuestionGuidance,
        has_gaps: bool,
    ) -> ResponseMode:
        if guidance == "defer":
            return "hold_space"
        if signal.recommended_response_mode in ("hold_space", "gentle_explore", "structured_gather"):
            if signal.recommended_response_mode == "hold_space" and has_gaps:
                return "gentle_explore"
            return signal.recommended_response_mode
        return "structured_gather" if has_gaps else "gentle_explore"

    @staticmethod
    def _build_directive_text(
        mode: ResponseMode,
        *,
        question_guidance: QuestionGuidance,
        pushback_type: PushbackType,
        min_sentences: int,
        max_question_words: int,
        suggested_focus_field: str | None,
        signal: DialogueSignalResult,
    ) -> str:
        focus_hint = f" Card area to explore: {suggested_focus_field}." if suggested_focus_field else ""
        lines = [
            f"Response mode for this turn: {mode}.",
            f"Write at least {min_sentences} complete sentences in patient_response_ru.",
            f"question_guidance: {question_guidance}.",
            f"Signal rationale: {signal.rationale_short or 'No short rationale provided.'}",
        ]
        if signal.crisis_signal:
            lines.append(
                "Crisis-level signal detected by dialogue analysis: prioritize safety, grounded "
                "empathic presence, and no information-gathering question this turn."
            )
        elif pushback_type == "stage":
            lines.append(
                "Stage pushback or premature advice request detected: apply the intake-stage "
                "boundary from system instructions, validate urgency, explain why context matters, "
                "and end with a patient-led invitation rather than a direct question."
                + focus_hint
            )
        elif pushback_type == "hard_stop":
            lines.append(
                "Patient requested no questions now: hold space, validate, and do not ask a direct "
                "question this turn."
                + focus_hint
            )
        elif question_guidance == "defer":
            lines.append("Do not ask a question this turn; use reflection and containment." + focus_hint)
        elif mode == "structured_gather":
            lines.append(
                f"Start with warm reflection, then include one soft open-ended question "
                f"(max {max_question_words} words) toward understanding or the intake card."
                f"{focus_hint}"
            )
        else:
            lines.append(
                f"Use empathic reflection and, if natural, one open-ended question "
                f"(max {max_question_words} words) that follows from the patient's words."
                f"{focus_hint}"
            )
        return " ".join(lines)

    @classmethod
    def compute_directives(
        cls,
        *,
        signal: DialogueSignalResult,
        therapist_styles: list[str] | None,
        missing_fields: list[str],
        min_sentences: int = 3,
        max_question_words: int = 25,
    ) -> TurnDirectives:
        has_gaps = len(missing_fields) >= 1
        suggested_focus = missing_fields[0] if missing_fields else None
        guidance = cls._resolve_guidance(signal, has_gaps)
        mode = cls._resolve_mode(signal, guidance, has_gaps)
        active_style = cls._resolve_style(signal, therapist_styles)
        min_s = max(min_sentences, 4 if signal.crisis_signal or guidance == "defer" else 3)
        allow_question = guidance != "defer"
        pushback_type = signal.pushback_type

        directive_en = cls._build_directive_text(
            mode,
            question_guidance=guidance,
            pushback_type=pushback_type,
            min_sentences=min_s,
            max_question_words=max_question_words,
            suggested_focus_field=suggested_focus,
            signal=signal,
        )

        return TurnDirectives(
            response_mode=mode,
            active_style=active_style,
            min_sentences=min_s,
            max_question_words=max_question_words,
            allow_question=allow_question,
            question_guidance=guidance,
            pushback_type=pushback_type,
            directive_en=directive_en,
            primary_emotion=signal.primary_emotion,
            emotional_intensity=signal.emotional_intensity,
            suggested_focus_field=suggested_focus,
            advice_request=signal.advice_request,
            crisis_signal=signal.crisis_signal,
            confidence=signal.confidence,
            rationale_short=signal.rationale_short,
        )
