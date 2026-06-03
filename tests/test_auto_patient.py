from monitoring.sandbox.auto_patient import build_auto_patient_messages, build_prescreening_generation_messages


def test_auto_patient_prompt_requires_russian_and_bold_patient_voice():
    messages = build_auto_patient_messages(
        start_phase="intake",
        prescreening_profile={"patient_name": "Иван"},
        generated_scenario={
            "persona_archetype": "тревожный профессионал",
            "presenting_problem": "Панические приступы перед работой",
        },
        conversation=[
            {"role": "assistant", "content": "Что вы чувствуете утром?"},
            {"role": "user", "content": "Мне тревожно."},
        ],
        turn_number=2,
        entropy="nonce:test",
    )

    system = messages[0]["content"]
    assert messages[0]["role"] == "system"
    assert "ВСЕГДА пиши только по-русски" in system
    assert "Не стесняйся" in system
    assert "тревожный профессионал" in system
    assert "Панические приступы перед работой" in system
    assert messages[-1]["role"] == "user"
    assert "следующую реплику пациента" in messages[-1]["content"]


def test_prescreening_generation_prompt_avoids_templates():
    messages = build_prescreening_generation_messages("seed-123")
    system = messages[0]["content"]
    assert "не повторяй шаблонные имена" in system.lower() or "не повторяй" in system.lower()
    assert "JSON" in system
