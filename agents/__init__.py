"""Agents module for Opora."""

from typing import TYPE_CHECKING

__all__ = [
    "TherapistAgent",
    "IntakeAgent",
    "TherapistEvaluator",
    "TherapistPrompts",
    "EvaluatorPrompts",
    "IntakePrompts",
]

if TYPE_CHECKING:
    from .core.intake_agent import IntakeAgent
    from .core.therapist_agent import TherapistAgent
    from .evaluators.therapist_evaluator import TherapistEvaluator
    from .prompts import EvaluatorPrompts, IntakePrompts, TherapistPrompts


def __getattr__(name: str):
    if name == "TherapistAgent":
        from .core.therapist_agent import TherapistAgent

        return TherapistAgent
    if name == "IntakeAgent":
        from .core.intake_agent import IntakeAgent

        return IntakeAgent
    if name == "TherapistEvaluator":
        from .evaluators.therapist_evaluator import TherapistEvaluator

        return TherapistEvaluator
    if name == "TherapistPrompts":
        from .prompts.therapist_prompts import TherapistPrompts

        return TherapistPrompts
    if name == "EvaluatorPrompts":
        from .prompts.evaluator_prompts import EvaluatorPrompts

        return EvaluatorPrompts
    if name == "IntakePrompts":
        from .prompts.intake_prompts import IntakePrompts

        return IntakePrompts
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
