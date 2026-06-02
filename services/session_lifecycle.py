"""Canonical lifecycle operations for therapy sessions."""

from __future__ import annotations

from dataclasses import dataclass

from db.repositories import ClinicalProfileRepository, IntakeStateRepository, SessionRepository


@dataclass(slots=True)
class CreatedSession:
    session_id: int
    session_number: int
    flow_phase: str
    card_filled: bool
    created_new: bool = True


async def get_or_create_active_session(
    *,
    account_id: int,
    intake_enabled: bool,
    session,
) -> CreatedSession:
    """Return the active session or create one without closing prior context."""
    session_repo = SessionRepository(session)
    intake_repo = IntakeStateRepository(session)
    clinical_repo = ClinicalProfileRepository(session)

    active_session = await session_repo.get_active_session(account_id)
    if active_session:
        intake_state = await intake_repo.get_by_session_id(active_session.id)
        card_filled = await clinical_repo.is_card_filled(account_id)
        return CreatedSession(
            session_id=active_session.id,
            session_number=active_session.session_number,
            flow_phase=(intake_state.flow_phase if intake_state else "therapy"),
            card_filled=card_filled,
            created_new=False,
        )

    latest_session = await session_repo.get_latest_session(account_id)
    new_session_number = (latest_session.session_number + 1) if latest_session else 1

    card_filled = await clinical_repo.is_card_filled(account_id)
    flow_phase = "intake" if intake_enabled and not card_filled else "therapy"

    new_session = await session_repo.create_session(
        account_id=account_id,
        session_number=new_session_number,
        therapy_type="unspecified therapy",
        therapy_reason=None,
    )
    await intake_repo.create_for_session(session_id=new_session.id, flow_phase=flow_phase)

    return CreatedSession(
        session_id=new_session.id,
        session_number=new_session_number,
        flow_phase=flow_phase,
        card_filled=card_filled,
        created_new=True,
    )


async def create_or_replace_active_session(
    *,
    account_id: int,
    intake_enabled: bool,
    session,
) -> CreatedSession:
    """Deprecated compatibility wrapper. It no longer closes active sessions."""
    return await get_or_create_active_session(
        account_id=account_id,
        intake_enabled=intake_enabled,
        session=session,
    )

