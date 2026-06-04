"""Static per-turn directives for intake without a separate analysis agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ResponseMode = Literal["hold_space", "gentle_explore", "structured_gather"]
QuestionGuidance = Literal["encourage", "optional", "defer"]


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
    suggested_focus_field: str | None = None


def build_default_directives(
    *,
    therapist_styles: list[str] | None,
    missing_fields: list[str],
    min_sentences: int = 3,
    max_question_words: int = 25,
) -> TurnDirectives:
    """Build intake turn directives from card gaps only."""
    styles = therapist_styles or []
    active_style = styles[0] if styles else "friendly"
    has_gaps = bool(missing_fields)
    suggested_focus = missing_fields[0] if missing_fields else None
    mode: ResponseMode = "structured_gather" if has_gaps else "gentle_explore"
    guidance: QuestionGuidance = "encourage" if has_gaps else "optional"
    focus_hint = f" Card area to explore: {suggested_focus}." if suggested_focus else ""
    directive_en = (
        f"Response mode for this turn: {mode}. "
        f"Write at least {min_sentences} complete sentences in patient_response_ru. "
        f"question_guidance: {guidance}. "
        f"Start with warm reflection, then include one soft open-ended question "
        f"(max {max_question_words} words) toward understanding or the intake card.{focus_hint}"
    )
    return TurnDirectives(
        response_mode=mode,
        active_style=active_style,
        min_sentences=min_sentences,
        max_question_words=max_question_words,
        allow_question=True,
        question_guidance=guidance,
        directive_en=directive_en,
        suggested_focus_field=suggested_focus,
    )
