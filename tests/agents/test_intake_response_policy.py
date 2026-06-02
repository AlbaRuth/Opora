"""Unit tests for IntakeResponsePolicy."""

from agents.intake.response_policy import IntakeResponsePolicy
from agents.prompts.intake_prompts import IntakePrompts


def test_crisis_intensity_defer():
    directives = IntakeResponsePolicy.compute_directives(
        patient_message="Мне очень тяжело, я не могу больше",
        therapist_styles=["friendly", "soft"],
        current_user_turns=2,
        primary_emotion="sadness",
        emotional_intensity=0.95,
        missing_fields=["current_problems"],
        recent_dialogue=None,
        hold_emotion_intensity_threshold=0.95,
    )
    assert directives.response_mode == "hold_space"
    assert directives.question_guidance == "defer"
    assert directives.pushback_type == "none"
    assert directives.allow_question is False


def test_moderate_sadness_still_encourages_question():
    directives = IntakeResponsePolicy.compute_directives(
        patient_message="Мне грустно и тревожно на работе",
        therapist_styles=["friendly", "soft"],
        current_user_turns=2,
        primary_emotion="sadness",
        emotional_intensity=0.8,
        missing_fields=["current_problems"],
        recent_dialogue=None,
        hold_emotion_intensity_threshold=0.95,
    )
    assert directives.question_guidance == "encourage"
    assert directives.pushback_type == "none"
    assert directives.allow_question is True
    assert "Still end with ONE soft open-ended question" in directives.directive_en


def test_stage_pushback_why_so_many_questions():
    directives = IntakeResponsePolicy.compute_directives(
        patient_message="Почему вы постоянно задаёте вопросы?",
        therapist_styles=["friendly"],
        current_user_turns=3,
        primary_emotion="anger",
        emotional_intensity=0.5,
        missing_fields=["current_problems"],
        recent_dialogue=None,
    )
    assert directives.pushback_type == "stage"
    assert directives.question_guidance == "defer"
    assert directives.allow_question is False
    assert "INTAKE_STAGE_PUSHBACK_HANDLING" in directives.directive_en


def test_stage_pushback_advice_request():
    directives = IntakeResponsePolicy.compute_directives(
        patient_message="Скажите что мне делать, хочу улучшить себя",
        therapist_styles=["friendly"],
        current_user_turns=2,
        primary_emotion="neutral",
        emotional_intensity=0.3,
        missing_fields=["current_problems"],
        recent_dialogue=None,
    )
    assert directives.pushback_type == "stage"
    assert directives.question_guidance == "defer"
    assert "upcoming" in directives.directive_en.lower() or "INTAKE_STAGE" in directives.directive_en


def test_hard_question_stop_defer():
    directives = IntakeResponsePolicy.compute_directives(
        patient_message="Перестаньте спрашивать, пожалуйста",
        therapist_styles=["friendly"],
        current_user_turns=4,
        primary_emotion="anger",
        emotional_intensity=0.5,
        missing_fields=["current_problems"],
        recent_dialogue=None,
    )
    assert directives.pushback_type == "hard_stop"
    assert directives.question_guidance == "defer"
    assert "stop questions" in directives.directive_en.lower()


def test_hvatit_voprosov_triggers_stage_not_hard_stop():
    directives = IntakeResponsePolicy.compute_directives(
        patient_message="Хватит вопросов, я устал",
        therapist_styles=["friendly"],
        current_user_turns=4,
        primary_emotion="anger",
        emotional_intensity=0.5,
        missing_fields=["current_problems"],
        recent_dialogue=None,
    )
    assert directives.pushback_type == "stage"
    assert "INTAKE_STAGE_PUSHBACK_HANDLING" in directives.directive_en


def test_many_counselor_questions_still_encourage():
    dialogue = [
        {"role": "user", "content": "работаю программистом"},
        {"role": "assistant", "content": "Расскажите подробнее?"},
        {"role": "user", "content": "уже пять лет"},
        {"role": "assistant", "content": "А как вы себя чувствуете?"},
        {"role": "user", "content": "нормально"},
        {"role": "assistant", "content": "Что для вас важно?"},
    ]
    directives = IntakeResponsePolicy.compute_directives(
        patient_message="нормально",
        therapist_styles=["business"],
        current_user_turns=3,
        primary_emotion="neutral",
        emotional_intensity=0.2,
        missing_fields=["current_problems"],
        recent_dialogue=dialogue,
    )
    assert directives.question_guidance == "encourage"
    assert directives.pushback_type == "none"


def test_missing_fields_structured_gather_encourage():
    directives = IntakeResponsePolicy.compute_directives(
        patient_message="работаю программистом",
        therapist_styles=["friendly"],
        current_user_turns=1,
        primary_emotion="neutral",
        emotional_intensity=0.2,
        missing_fields=["mental_health_history"],
        recent_dialogue=None,
    )
    assert directives.response_mode == "structured_gather"
    assert directives.question_guidance == "encourage"
    assert directives.suggested_focus_field == "mental_health_history"


def test_global_prompt_includes_pushback_handling():
    instructions = IntakePrompts.build_global_system_instructions()
    assert "INTAKE STAGE PUSHBACK" in instructions
    assert "will NOT give advice" in instructions
    assert "upcoming therapy sessions" in instructions
