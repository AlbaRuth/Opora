"""
Turn-level response directives for IntakeAgent.

Returns modes and constraints for the LLM — never canned patient-facing questions.

Intake note: emotion evaluation informs tone and reflection length, but must NOT
suppress questions except true crisis or explicit patient pushback on questioning.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agents.prompts.intake_prompts import IntakePrompts

ResponseMode = Literal["hold_space", "gentle_explore", "structured_gather"]
QuestionGuidance = Literal["encourage", "optional", "defer"]
PushbackType = Literal["none", "stage", "hard_stop"]

_NEGATIVE_EMOTIONS = frozenset({"sadness", "anxiety", "fear", "anger", "disgust", "hurt"})
_CRISIS_KEYWORDS = (
    "не могу больше",
    "не хочу жить",
    "хочу умереть",
    "хочу покончить",
    "покончить с собой",
    "покончить с жизнью",
    "суицид",
    "самоубийств",
    "убью себя",
    "кончаю с собой",
    "лучше бы меня не было",
)
_STAGE_PUSHBACK_KEYWORDS = (
    "почему столько вопрос",
    "почему вы постоянно спрашива",
    "почему ты постоянно спрашива",
    "почему так много вопрос",
    "зачем столько вопрос",
    "зачем вы спрашива",
    "зачем ты спрашива",
    "хватит вопрос",
    "хватит допрашивать",
    "хватит меня допрашивать",
    "достало вопрос",
    "слишком много вопрос",
    "постоянно спрашиваете",
    "постоянно спрашиваешь",
    "постоянно задаёте",
    "постоянно задаете",
    "задаёте вопрос",
    "задаете вопрос",
    "перейдём к делу",
    "перейдем к делу",
    "давай к делу",
    "давайте к делу",
    "что мне делать",
    "что делать чтобы",
    "как мне улучшить",
    "как улучшить себя",
    "дай совет",
    "дайте совет",
    "хочу совет",
    "нужен совет",
    "сколько можно спрашивать",
)
_HARD_QUESTION_STOP_KEYWORDS = (
    "перестань спрашивать",
    "перестаньте спрашивать",
    "не хочу отвечать на вопрос",
    "задолбали вопрос",
    "надоело отвечать",
    "надоело, что спрашива",
    "устал отвечать",
    "устала отвечать",
)


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


class IntakeResponsePolicy:
    """Computes intake turn directives from emotion, dialogue, and card state."""

    @staticmethod
    def _detect_pushback(message: str) -> PushbackType:
        text = message.lower()
        if any(kw in text for kw in _STAGE_PUSHBACK_KEYWORDS):
            return "stage"
        if any(kw in text for kw in _HARD_QUESTION_STOP_KEYWORDS):
            return "hard_stop"
        return "none"

    @staticmethod
    def _message_signals_crisis(message: str) -> bool:
        text = message.lower()
        return any(kw in text for kw in _CRISIS_KEYWORDS)

    @staticmethod
    def _emotion_signals_crisis(
        primary_emotion: str,
        emotional_intensity: float,
        crisis_intensity_threshold: float,
    ) -> bool:
        emotion = (primary_emotion or "").lower().strip()
        return (
            emotion in _NEGATIVE_EMOTIONS
            and emotional_intensity >= crisis_intensity_threshold
        )

    @staticmethod
    def _is_emotionally_weighted_turn(
        primary_emotion: str,
        emotional_intensity: float,
    ) -> bool:
        emotion = (primary_emotion or "").lower().strip()
        if emotion in _NEGATIVE_EMOTIONS and emotional_intensity >= 0.5:
            return True
        return emotional_intensity >= 0.65

    @staticmethod
    def _resolve_style_from_emotion(
        primary_emotion: str,
        emotional_intensity: float,
        therapist_styles: list[str] | None,
        keyword_style: str,
    ) -> str:
        styles = therapist_styles or []
        if not styles:
            return keyword_style or "friendly"

        emotion = (primary_emotion or "").lower().strip()
        if emotion in _NEGATIVE_EMOTIONS and emotional_intensity >= 0.5:
            if "soft" in styles:
                return "soft"

        return keyword_style if keyword_style in styles else styles[0]

    @staticmethod
    def _build_directive_text(
        mode: ResponseMode,
        *,
        question_guidance: QuestionGuidance,
        pushback_type: PushbackType,
        min_sentences: int,
        max_question_words: int,
        suggested_focus_field: str | None,
        emotionally_weighted: bool,
    ) -> str:
        lines = [
            f"Response mode for this turn: {mode}.",
            f"Write at least {min_sentences} complete sentences in patient_response_ru.",
            f"question_guidance: {question_guidance}.",
        ]
        focus_hint = ""
        if suggested_focus_field:
            focus_hint = f" Card area to explore: {suggested_focus_field}."

        if pushback_type == "stage":
            lines.append(
                "PUSHBACK DETECTED — apply INTAKE_STAGE_PUSHBACK_HANDLING from system instructions. "
                "Validate frustration or urgency; explain intake vs later therapy; no advice or "
                "action plans now; orient to upcoming sessions working on their problems together. "
                "End with a patient-led invitation in their own pace — no direct question mark "
                "on this turn. Resume gentle gathering on later turns if they engage."
                + focus_hint
            )
        elif pushback_type == "hard_stop":
            lines.append(
                "Patient asked to stop questions: prioritize empathic holding space only — "
                "no direct question this turn. Brief validation; do not pressure them to answer."
                + focus_hint
            )
        elif question_guidance == "defer":
            lines.append(
                "This turn: prioritize holding space and empathic reflection only — "
                "no direct question (crisis-level distress)."
                + focus_hint
            )
        elif emotionally_weighted:
            lines.append(
                "The patient is in pain or strong emotion: lead with extended empathic "
                "reflection and validation (most of your reply). "
                f"Still end with ONE soft open-ended question (max {max_question_words} words) "
                "when they can engage — intake requires understanding, not silence."
                f"{focus_hint}"
            )
        elif mode == "structured_gather":
            lines.append(
                "Start with warm reflection on what they shared. "
                f"Then include ONE soft open-ended question (max {max_question_words} words) "
                "toward a missing card area — expected on intake."
                f"{focus_hint} "
                "Never open with name + single blunt question."
            )
        else:
            lines.append(
                "Start with reflection on what they shared. "
                f"Then include ONE soft open-ended question (max {max_question_words} words) "
                "that advances understanding or the intake card."
                f"{focus_hint} "
                "The question must follow from their words, not a generic intake script."
            )
        return " ".join(lines)

    @classmethod
    def compute_directives(
        cls,
        *,
        patient_message: str,
        therapist_styles: list[str] | None,
        current_user_turns: int,
        primary_emotion: str,
        emotional_intensity: float,
        missing_fields: list[str],
        recent_dialogue: list[dict[str, str]] | None,
        min_sentences: int = 3,
        max_question_words: int = 25,
        hold_emotion_intensity_threshold: float = 0.95,
        max_user_turns: int | None = None,
    ) -> TurnDirectives:
        _ = recent_dialogue
        keyword_style = IntakePrompts.resolve_active_style(
            patient_message, therapist_styles, current_user_turns
        )
        active_style = cls._resolve_style_from_emotion(
            primary_emotion,
            emotional_intensity,
            therapist_styles,
            keyword_style,
        )

        has_gaps = len(missing_fields) >= 1
        suggested_focus = missing_fields[0] if missing_fields else None
        emotionally_weighted = cls._is_emotionally_weighted_turn(
            primary_emotion, emotional_intensity
        )
        pushback_type = cls._detect_pushback(patient_message)

        near_max = (
            max_user_turns is not None
            and current_user_turns >= max(0, max_user_turns - 2)
        )

        crisis = cls._message_signals_crisis(patient_message) or cls._emotion_signals_crisis(
            primary_emotion,
            emotional_intensity,
            hold_emotion_intensity_threshold,
        )

        if crisis:
            mode: ResponseMode = "hold_space"
            guidance: QuestionGuidance = "defer"
            pushback_type = "none"
            min_s = max(min_sentences, 4)
        elif pushback_type == "stage":
            mode = "hold_space"
            guidance = "defer"
            min_s = max(min_sentences, 4)
        elif pushback_type == "hard_stop":
            mode = "hold_space"
            guidance = "defer"
            min_s = max(min_sentences, 3)
        elif has_gaps:
            mode = "structured_gather"
            guidance = "encourage"
            pushback_type = "none"
            min_s = max(min_sentences, 4 if emotionally_weighted else 3)
            if near_max:
                min_s = max(min_sentences, 3)
        else:
            mode = "gentle_explore"
            guidance = "encourage"
            pushback_type = "none"
            min_s = max(min_sentences, 4 if emotionally_weighted else 3)

        allow_question = guidance != "defer"

        directive_en = cls._build_directive_text(
            mode,
            question_guidance=guidance,
            pushback_type=pushback_type,
            min_sentences=min_s,
            max_question_words=max_question_words,
            suggested_focus_field=suggested_focus,
            emotionally_weighted=emotionally_weighted and allow_question,
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
            primary_emotion=primary_emotion,
            emotional_intensity=emotional_intensity,
            suggested_focus_field=suggested_focus,
        )
