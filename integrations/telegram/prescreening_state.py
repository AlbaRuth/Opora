"""Persistent state adapter for prescreening wizard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from db.repositories import AccountRepository, PrescreeningStateRepository
from db.session import get_db_session


@dataclass(slots=True)
class PrescreeningWizardState:
    account_id: int
    step: str = "awaiting_therapist_name"
    therapist_name: str = "Опора"
    therapist_gender: str = "female"
    patient_name: str = ""
    patient_age: int | None = None
    patient_sex: str = "prefer_not_to_say"
    address_mode: str = "formal"
    selected_styles: list[str] = field(default_factory=list)
    is_edit_mode: bool = False
    processing_started_at: datetime | None = None


async def get_account_id_by_telegram_id(telegram_id: int) -> int | None:
    async with get_db_session() as session:
        account_repo = AccountRepository(session)
        account = await account_repo.get_by_telegram_id(telegram_id)
        return account.id if account else None


async def get_wizard_state(telegram_id: int) -> PrescreeningWizardState | None:
    account_id = await get_account_id_by_telegram_id(telegram_id)
    if not account_id:
        return None
    async with get_db_session() as session:
        repo = PrescreeningStateRepository(session)
        record = await repo.get_by_account_id(account_id)
        if not record:
            return None
        return PrescreeningWizardState(
            account_id=account_id,
            step=record.step,
            therapist_name=record.therapist_name,
            therapist_gender=record.therapist_gender,
            patient_name=record.patient_name,
            patient_age=record.patient_age,
            patient_sex=record.patient_sex,
            address_mode=record.address_mode,
            selected_styles=list(record.selected_styles or []),
            is_edit_mode=record.is_edit_mode,
            processing_started_at=record.processing_started_at,
        )


async def save_wizard_state(state: PrescreeningWizardState) -> None:
    async with get_db_session() as session:
        repo = PrescreeningStateRepository(session)
        await repo.upsert(
            account_id=state.account_id,
            step=state.step,
            therapist_name=state.therapist_name,
            therapist_gender=state.therapist_gender,
            patient_name=state.patient_name,
            patient_age=state.patient_age,
            patient_sex=state.patient_sex,
            address_mode=state.address_mode,
            selected_styles=state.selected_styles,
            is_edit_mode=state.is_edit_mode,
            processing_started_at=state.processing_started_at,
        )


async def clear_wizard_state(telegram_id: int) -> None:
    account_id = await get_account_id_by_telegram_id(telegram_id)
    if not account_id:
        return
    async with get_db_session() as session:
        repo = PrescreeningStateRepository(session)
        await repo.delete_by_account_id(account_id)


async def is_in_prescreening(telegram_id: int) -> bool:
    return (await get_wizard_state(telegram_id)) is not None

