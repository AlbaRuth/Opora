"""Canonical mappings for profile-related display labels."""

from __future__ import annotations

from typing import Final

THERAPIST_STYLES: Final[list[tuple[str, str]]] = [
    ("friendly", "Дружелюбный"),
    ("soft", "Мягкий"),
    ("business", "Деловой"),
    ("motivating", "Мотивирующий"),
]

DEFAULT_THERAPIST_NAME: Final[str] = "Опора"
DEFAULT_THERAPIST_GENDER: Final[str] = "female"


def style_labels(style_ids: list[str]) -> list[str]:
    style_map = dict(THERAPIST_STYLES)
    return [style_map.get(style_id, style_id) for style_id in style_ids]


def sex_label(sex: str | None) -> str:
    mapping = {
        "male": "Мужской",
        "female": "Женский",
        "prefer_not_to_say": "Не указан",
    }
    return mapping.get(sex or "", "Не указан")


def address_mode_label(mode: str | None) -> str:
    mapping = {
        "formal": "На 'Вы'",
        "informal": "На 'Ты'",
    }
    return mapping.get(mode or "", "На 'Вы'")

