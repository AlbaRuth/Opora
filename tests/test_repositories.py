"""Integration tests for DB repositories (v2 schema)."""

import pytest

from db.repositories import (
    AccountRepository,
    ClinicalProfileRepository,
    SessionRepository,
)


@pytest.mark.asyncio
async def test_account_create_from_telegram_creates_profiles(db_session):
    repo = AccountRepository(db_session)
    account = await repo.create_from_telegram(
        telegram_id=77001,
        username="u1",
        first_name="F",
        last_name="L",
        language_code="ru",
    )
    assert account.id is not None
    assert account.telegram_id == 77001

    loaded = await repo.get_by_telegram_id(77001)
    assert loaded is not None
    assert loaded.user_profile is not None
    assert loaded.therapist_preference is not None
    assert loaded.clinical_profile is not None
    assert loaded.clinical_profile.account_id == loaded.id


@pytest.mark.asyncio
async def test_session_repository_create_and_latest(db_session):
    acc_repo = AccountRepository(db_session)
    account = await acc_repo.create_from_telegram(telegram_id=77002)

    sess_repo = SessionRepository(db_session)
    s1 = await sess_repo.create_session(
        account_id=account.id,
        session_number=1,
        therapy_type="cbt",
        therapy_reason="test",
    )
    assert s1.session_number == 1
    assert s1.is_active is True

    latest = await sess_repo.get_latest_session(account.id)
    assert latest is not None
    assert latest.id == s1.id

    s2 = await sess_repo.create_session(
        account_id=account.id,
        session_number=2,
        therapy_type="cbt",
    )
    latest2 = await sess_repo.get_latest_session(account.id)
    assert latest2 is not None
    assert latest2.session_number == 2


@pytest.mark.asyncio
async def test_session_repository_increment_dialog_count(db_session):
    acc_repo = AccountRepository(db_session)
    account = await acc_repo.create_from_telegram(telegram_id=77003)
    sess_repo = SessionRepository(db_session)
    s = await sess_repo.create_session(account_id=account.id, session_number=1)
    updated = await sess_repo.increment_dialog_count(s.id)
    assert updated is not None
    assert updated.dialog_count == 1


@pytest.mark.asyncio
async def test_clinical_profile_update_and_card_filled(db_session):
    acc_repo = AccountRepository(db_session)
    account = await acc_repo.create_from_telegram(telegram_id=77004)
    clinical_repo = ClinicalProfileRepository(db_session)

    assert await clinical_repo.is_card_filled(account.id) is False

    await clinical_repo.update_clinical_data(
        account_id=account.id,
        current_problems="insomnia",
    )
    assert await clinical_repo.is_card_filled(account.id) is True

    record = await clinical_repo.get_patient_record(account.id)
    assert record is not None
    assert "insomnia" in record["current_problems"]
