"""Centralized access gate for prescreening status."""

from __future__ import annotations

from dataclasses import dataclass

from db.repositories import AccountRepository, TherapistPreferenceRepository


@dataclass(slots=True)
class PrescreeningGateResult:
    account_exists: bool
    account_id: int | None
    is_complete: bool


async def evaluate_prescreening_gate(telegram_id: int, session) -> PrescreeningGateResult:
    account_repo = AccountRepository(session)
    pref_repo = TherapistPreferenceRepository(session)

    account = await account_repo.get_by_telegram_id(telegram_id)
    if not account:
        return PrescreeningGateResult(account_exists=False, account_id=None, is_complete=False)

    is_complete = await pref_repo.is_prescreening_complete(account.id)
    return PrescreeningGateResult(
        account_exists=True,
        account_id=account.id,
        is_complete=is_complete,
    )

