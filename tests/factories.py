"""Test data factories for v2 schema (async, use with db_session)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import (
    AccountRepository,
    ClinicalProfileRepository,
    SessionRepository,
    TherapistPreferenceRepository,
    UserProfileRepository,
    IntakeStateRepository,
)


async def create_account_with_prescreening(
    session: AsyncSession,
    telegram_id: int,
    *,
    therapist_name: str = "Анна",
    therapist_gender: str = "female",
    therapist_traits: list[str] | None = None,
    patient_display_name: str | None = "Иван",
    patient_age: int | None = 30,
    patient_sex: str | None = "prefer_not_to_say",
    address_mode: str = "formal",
    mark_prescreening_complete: bool = True,
):
    """Create Account with nested profiles; optionally complete prescreening."""
    acc_repo = AccountRepository(session)
    account = await acc_repo.create_from_telegram(telegram_id=telegram_id)
    pref_repo = TherapistPreferenceRepository(session)
    profile_repo = UserProfileRepository(session)
    traits = therapist_traits if therapist_traits is not None else ["calm"]
    await pref_repo.update_preferences(
        account.id,
        therapist_name=therapist_name,
        therapist_gender=therapist_gender,
        therapist_traits=traits,
        mark_complete=mark_prescreening_complete,
    )
    await profile_repo.update_profile(
        account.id,
        display_name=patient_display_name,
        age=patient_age,
        sex=patient_sex,
        address_mode=address_mode,
    )
    return account


async def create_active_therapy_session(
    session: AsyncSession,
    account_id: int,
    *,
    session_number: int = 1,
    flow_phase: str = "therapy",
) -> tuple:
    """Return (TherapySession, IntakeState | None)."""
    sess_repo = SessionRepository(session)
    ts = await sess_repo.create_session(
        account_id=account_id,
        session_number=session_number,
    )
    intake_repo = IntakeStateRepository(session)
    intake = await intake_repo.create_for_session(
        session_id=ts.id,
        flow_phase=flow_phase,
    )
    return ts, intake


async def fill_clinical_card_minimal(
    session: AsyncSession,
    account_id: int,
    *,
    current_problems: str = "Anxiety",
    mental_health_history: str | None = None,
):
    clinical_repo = ClinicalProfileRepository(session)
    await clinical_repo.update_clinical_data(
        account_id=account_id,
        current_problems=current_problems,
        mental_health_history=mental_health_history,
    )
