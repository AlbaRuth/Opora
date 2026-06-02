"""Pure helpers for prescreening step transitions and formatting."""

from __future__ import annotations

from core.profile_labels import address_mode_label, sex_label, style_labels


def migrate_traits_to_styles(traits: list[str] | None) -> list[str]:
    if not traits:
        return []
    trait_to_style = {
        "strict": "business",
        "business": "business",
        "calm": "soft",
        "kind": "friendly",
        "restrained": "soft",
        "empathetic": "friendly",
    }
    migrated: list[str] = []
    for trait in traits:
        style = trait_to_style.get(trait)
        if style and style not in migrated:
            migrated.append(style)
    return migrated if migrated else ["friendly"]


def build_completion_profile_lines(
    *,
    therapist_name: str,
    therapist_gender: str,
    patient_name: str,
    patient_age: int | None,
    patient_sex: str,
    address_mode: str,
    selected_styles: list[str],
) -> list[str]:
    gender_label = "Женский" if therapist_gender == "female" else "Мужской"
    styles = style_labels(selected_styles)
    return [
        "✅ <b>Профиль обновлен!</b>",
        "",
        f"🧠 Имя психолога: {therapist_name}",
        f"⚧ Пол психолога: {gender_label}",
        "",
        f"👤 Ваше имя: {patient_name}",
        f"🎂 Возраст: {patient_age}",
        f"⚥ Ваш пол: {sex_label(patient_sex)}",
        f"💬 Обращение: {address_mode_label(address_mode)}",
        f"✨ Стиль общения: {', '.join(styles)}",
    ]

