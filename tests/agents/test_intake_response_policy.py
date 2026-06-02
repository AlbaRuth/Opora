"""Unit tests for IntakeResponsePolicy."""

from agents.evaluators.structured_outputs import DialogueSignalResult
from agents.intake.response_policy import IntakeResponsePolicy
from agents.prompts.intake_prompts import IntakePrompts


def test_crisis_signal_defer():
    directives = IntakeResponsePolicy.compute_directives(
        signal=DialogueSignalResult(
            primary_emotion="sadness",
            emotional_intensity=0.95,
            crisis_signal=True,
            question_guidance="defer",
            recommended_response_mode="hold_space",
        ),
        therapist_styles=["friendly", "soft"],
        missing_fields=["current_problems"],
    )
    assert directives.response_mode == "hold_space"
    assert directives.question_guidance == "defer"
    assert directives.allow_question is False
    assert directives.crisis_signal is True


def test_moderate_distress_still_encourages_question_when_gaps_remain():
    directives = IntakeResponsePolicy.compute_directives(
        signal=DialogueSignalResult(
            primary_emotion="sadness",
            emotional_intensity=0.8,
            active_style="soft",
            question_guidance="encourage",
            recommended_response_mode="structured_gather",
        ),
        therapist_styles=["friendly", "soft"],
        missing_fields=["current_problems"],
    )
    assert directives.question_guidance == "encourage"
    assert directives.allow_question is True
    assert directives.active_style == "soft"
    assert directives.suggested_focus_field == "current_problems"


def test_stage_pushback_defer():
    directives = IntakeResponsePolicy.compute_directives(
        signal=DialogueSignalResult(
            pushback_type="stage",
            advice_request=True,
            question_guidance="defer",
            recommended_response_mode="hold_space",
        ),
        therapist_styles=["friendly"],
        missing_fields=["current_problems"],
    )
    assert directives.pushback_type == "stage"
    assert directives.question_guidance == "defer"
    assert directives.allow_question is False


def test_hard_question_stop_defer():
    directives = IntakeResponsePolicy.compute_directives(
        signal=DialogueSignalResult(
            pushback_type="hard_stop",
            question_stop=True,
            question_guidance="defer",
        ),
        therapist_styles=["friendly"],
        missing_fields=["current_problems"],
    )
    assert directives.pushback_type == "hard_stop"
    assert directives.question_guidance == "defer"
    assert "no questions" in directives.directive_en.lower()


def test_missing_fields_structured_gather_encourage():
    directives = IntakeResponsePolicy.compute_directives(
        signal=DialogueSignalResult(
            question_guidance="encourage",
            recommended_response_mode="structured_gather",
        ),
        therapist_styles=["friendly"],
        missing_fields=["mental_health_history"],
    )
    assert directives.response_mode == "structured_gather"
    assert directives.question_guidance == "encourage"
    assert directives.suggested_focus_field == "mental_health_history"


def test_global_prompt_includes_pushback_handling():
    instructions = IntakePrompts.build_global_system_instructions()
    assert "INTAKE STAGE PUSHBACK" in instructions
    assert "will NOT give advice" in instructions
    assert "upcoming therapy sessions" in instructions
