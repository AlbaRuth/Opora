"""Tests for scripted intake user copy."""


def test_build_intake_start_message_same_min_max_formal():
    from core.intake_user_copy import build_intake_start_message

    text = build_intake_start_message(
        patient_name="Иван",
        address_mode="formal",
        therapist_gender="female",
        min_user_turns=6,
        max_user_turns=6,
    )
    assert "6" in text
    assert "ваших сообщений" in text
    assert "от 6 до 6" not in text


def test_build_intake_start_message_range_informal():
    from core.intake_user_copy import build_intake_start_message

    text = build_intake_start_message(
        patient_name="Мария",
        address_mode="informal",
        therapist_gender="male",
        min_user_turns=3,
        max_user_turns=9,
    )
    assert "от 3 до 9" in text
    assert "твоих сообщений" in text


def test_build_intake_start_message_clamps_invalid_range():
    from core.intake_user_copy import build_intake_start_message

    text = build_intake_start_message("", "formal", "female", 5, 2)
    assert "заложено 5 ваших сообщений" in text


def test_build_intake_completion_notice_normal_formal():
    from core.intake_user_copy import build_intake_completion_notice

    text = build_intake_completion_notice("formal", initial_info_insufficient=False)
    assert "/summary" in text
    assert "основную информацию" in text.lower()
    assert "введите" in text.lower()


def test_build_intake_completion_notice_normal_informal():
    from core.intake_user_copy import build_intake_completion_notice

    text = build_intake_completion_notice("informal", initial_info_insufficient=False)
    assert "/summary" in text
    assert "набери" in text.lower()


def test_build_intake_completion_notice_insufficient_formal():
    from core.intake_user_copy import build_intake_completion_notice

    text = build_intake_completion_notice("formal", initial_info_insufficient=True)
    assert "/summary" in text
    assert "первый этап" in text.lower()
    assert "основную информацию мы собрали" not in text.lower()
