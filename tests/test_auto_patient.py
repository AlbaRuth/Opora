from monitoring.sandbox.auto_patient import PatientTemplate, build_auto_patient_messages


def test_auto_patient_prompt_keeps_model_in_patient_role():
    template = PatientTemplate(
        name="Тревожный пациент",
        persona="32 года, говорит коротко и неохотно",
        presenting_problem="Панические приступы перед работой",
        hidden_facts=["недавно был конфликт с руководителем"],
        emotional_trajectory="сначала настороженность, затем чуть больше доверия",
        cooperation_level="уклончивый",
        safety_boundaries=["не описывать самоповреждение"],
        max_turns=6,
        stop_conditions=["терапевт завершил сессию"],
    )

    messages = build_auto_patient_messages(
        template=template,
        start_phase="intake",
        prescreening_profile={"patient_name": "Иван"},
        generated_scenario={"presenting_problem": "Панические приступы перед работой"},
        conversation=[
            {"role": "assistant", "content": "Что вы чувствуете утром?"},
            {"role": "user", "content": "Мне тревожно."},
        ],
    )

    assert messages[0]["role"] == "system"
    assert "You simulate a living patient" in messages[0]["content"]
    assert "Write only the next patient message" in messages[0]["content"]
    assert "Панические приступы перед работой" in messages[0]["content"]
    assert messages[-1]["role"] == "user"
    assert "Write the next patient message only" in messages[-1]["content"]
