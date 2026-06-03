"""Shared formatting for clinical card text shown to patients and in Monitor."""

from __future__ import annotations

CARD_FIELD_KEYS = (
    "current_problems",
    "mental_health_history",
    "physical_health_history",
    "intake_hypothesis",
    "intake_hypothesis_explanation",
)


def truncate_words(text: str, max_words: int) -> str:
    """Trim text to max_words, appending ellipsis when truncated."""
    if max_words <= 0:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def format_clinical_card_fields(card: dict[str, str]) -> str:
    """Format clinical card fields for display (Russian labels)."""
    return (
        f"Текущие проблемы и симптомы:\n{card.get('current_problems') or 'не указано'}\n\n"
        f"История психического здоровья:\n{card.get('mental_health_history') or 'не указано'}\n\n"
        f"История физического здоровья:\n{card.get('physical_health_history') or 'не указано'}\n\n"
        f"Предварительная клиническая гипотеза:\n{card.get('intake_hypothesis') or 'не указано'}\n\n"
        f"Пояснение:\n{card.get('intake_hypothesis_explanation') or 'не указано'}"
    )


def format_full_patient_summary(
    *,
    card: dict[str, str],
    display_name: str,
    age: str,
    sex_display: str,
) -> str:
    """Full /summary-style card text including demographics."""
    return (
        f"Сводка карточки пациента\n\n"
        f"Имя/псевдоним: {display_name}\n"
        f"Возраст: {age}\n"
        f"Пол: {sex_display}\n\n"
        f"{format_clinical_card_fields(card)}"
    )


def card_has_clinical_data(card: dict[str, str]) -> bool:
    """Return True if any clinical card field has content."""
    return any(card.get(key, "").strip() for key in CARD_FIELD_KEYS)
