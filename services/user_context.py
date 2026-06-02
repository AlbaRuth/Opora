"""Typed user context loading for dialogue orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from db.repositories import (
    ClinicalProfileRepository,
    TherapistPreferenceRepository,
    UserProfileRepository,
)


@dataclass(slots=True)
class UserContext:
    account_id: int
    therapist_name: str = "Опора"
    therapist_gender: str = "female"
    therapist_styles: list[str] = field(default_factory=list)
    patient_display_name: str = ""
    patient_age: int | None = None
    patient_sex: str = "prefer_not_to_say"
    address_mode: str = "formal"
    card_filled: bool = False


async def load_user_context(account_id: int, session) -> UserContext:
    """Load normalized user context for dialogue and session-state building."""
    profile_repo = UserProfileRepository(session)
    pref_repo = TherapistPreferenceRepository(session)
    clinical_repo = ClinicalProfileRepository(session)

    profile = await profile_repo.get_by_account_id(account_id)
    pref = await pref_repo.get_by_account_id(account_id)
    card_filled = await clinical_repo.is_card_filled(account_id)

    return UserContext(
        account_id=account_id,
        therapist_name=(pref.therapist_name if pref else None) or "Опора",
        therapist_gender=(pref.therapist_gender if pref else None) or "female",
        therapist_styles=(pref.therapist_traits if pref else None) or [],
        patient_display_name=(profile.effective_display_name if profile else None) or "",
        patient_age=profile.age if profile else None,
        patient_sex=(profile.sex if profile else None) or "prefer_not_to_say",
        address_mode=(profile.address_mode if profile else None) or "formal",
        card_filled=card_filled,
    )

