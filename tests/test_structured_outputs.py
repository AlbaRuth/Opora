from agents.evaluators.structured_outputs import (
    DialogueSignalResult,
    SandboxPrescreeningProfile,
    SandboxScenario,
    validate_model,
)


def test_dialogue_signal_result_validates_bounds_and_defaults():
    parsed = validate_model(
        DialogueSignalResult,
        {
            "primary_emotion": "sadness",
            "emotional_intensity": 0.7,
            "active_style": "soft",
            "confidence": 0.8,
        },
    )
    assert isinstance(parsed, DialogueSignalResult)
    assert parsed.primary_emotion == "sadness"
    assert parsed.active_style == "soft"
    assert parsed.pushback_type == "none"


def test_prescreening_profile_normalizes_styles():
    parsed = validate_model(
        SandboxPrescreeningProfile,
        {
            "patient_name": "Мария",
            "patient_age": 29,
            "patient_sex": "female",
            "address_mode": "formal",
            "therapist_name": "Опора",
            "therapist_gender": "female",
            "therapist_styles": ["unknown"],
            "scenario_brief": "Рабочее выгорание",
        },
    )
    assert isinstance(parsed, SandboxPrescreeningProfile)
    assert parsed.therapist_styles == ["friendly"]


def test_sandbox_scenario_accepts_generated_card_fields():
    parsed = validate_model(
        SandboxScenario,
        {
            "presenting_problem": "Тревога перед работой",
            "mental_health_history": "Ранее обращений не было",
            "physical_health_history": "Хронических заболеваний не указано",
            "current_problems": "Паника по утрам",
            "intake_hypothesis": "Предварительно тревожный паттерн",
            "intake_hypothesis_explanation": "Нужна дальнейшая проверка",
            "hidden_context": ["конфликт с руководителем"],
            "emotional_arc": "постепенно раскрывается",
            "cooperation_style": "осторожный",
        },
    )
    assert isinstance(parsed, SandboxScenario)
    assert parsed.hidden_context == ["конфликт с руководителем"]
