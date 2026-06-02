"""Integration tests for Account / prescreening repositories (v2 schema)."""

from datetime import datetime

import pytest

from db.repositories import (
    AccountRepository,
    ClinicalProfileRepository,
    TherapistPreferenceRepository,
    UserProfileRepository,
)
from tests.factories import create_account_with_prescreening


@pytest.mark.asyncio
class TestTherapistPreferenceRepository:
    async def test_update_prescreening_profile(self, db_session):
        account = await create_account_with_prescreening(
            db_session,
            12345,
            mark_prescreening_complete=False,
        )
        pref_repo = TherapistPreferenceRepository(db_session)
        pref = await pref_repo.get_by_account_id(account.id)
        assert pref is not None
        assert pref.is_prescreening_complete is False

        updated = await pref_repo.update_preferences(
            account.id,
            therapist_name="Доктор Анна",
            therapist_gender="female",
            therapist_styles=["friendly", "soft"],
            mark_complete=False,
        )
        assert updated is not None
        assert updated.therapist_name == "Доктор Анна"
        assert updated.therapist_gender == "female"
        assert updated.therapist_styles == ["friendly", "soft"]

    async def test_mark_prescreening_complete(self, db_session):
        account = await create_account_with_prescreening(
            db_session,
            12346,
            mark_prescreening_complete=False,
        )
        pref_repo = TherapistPreferenceRepository(db_session)
        updated = await pref_repo.update_preferences(
            account.id,
            therapist_name="Доктор Иван",
            therapist_gender="male",
            therapist_styles=["business"],
            mark_complete=True,
        )
        assert updated is not None
        assert updated.is_prescreening_complete is True
        assert updated.prescreening_completed_at is not None
        assert isinstance(updated.prescreening_completed_at, datetime)

    async def test_is_prescreening_complete_flags(self, db_session):
        account = await create_account_with_prescreening(db_session, 12347)
        pref_repo = TherapistPreferenceRepository(db_session)
        assert await pref_repo.is_prescreening_complete(account.id) is True

        account2 = await create_account_with_prescreening(
            db_session, 12348, mark_prescreening_complete=False
        )
        assert await pref_repo.is_prescreening_complete(account2.id) is False

    async def test_update_preferences_not_found(self, db_session):
        pref_repo = TherapistPreferenceRepository(db_session)
        assert await pref_repo.update_preferences(999999, therapist_name="x") is None


@pytest.mark.asyncio
class TestUserProfileAndClinicalIntegration:
    async def test_user_profile_update_display(self, db_session):
        account = await create_account_with_prescreening(db_session, 22345)
        profile_repo = UserProfileRepository(db_session)
        await profile_repo.update_profile(
            account.id,
            display_name="Петр",
            age=35,
            sex="male",
            address_mode="informal",
        )
        prof = await profile_repo.get_by_account_id(account.id)
        assert prof.effective_display_name == "Петр"
        assert prof.age == 35
        assert prof.address_mode == "informal"

    async def test_clinical_update_via_repository(self, db_session):
        account = await create_account_with_prescreening(db_session, 22346)
        clinical_repo = ClinicalProfileRepository(db_session)
        await clinical_repo.update_clinical_data(
            account_id=account.id,
            mental_health_history="История",
            current_problems="Проблемы",
        )
        assert await clinical_repo.is_card_filled(account.id) is True
        record = await clinical_repo.get_patient_record(account.id)
        assert record is not None
        assert "Проблемы" in (record.get("current_problems") or "")

    async def test_account_get_by_telegram_with_profiles(self, db_session):
        tid = 32345
        await create_account_with_prescreening(db_session, tid, patient_display_name="Мария")
        acc_repo = AccountRepository(db_session)
        loaded = await acc_repo.get_by_telegram_id(tid)
        assert loaded is not None
        assert loaded.user_profile is not None
        assert loaded.clinical_profile is not None


@pytest.mark.asyncio
class TestAccountRepositoryDelete:
    """Test AccountRepository.delete_by_telegram_id method."""

    async def test_delete_by_telegram_id_deletes_existing_account(self, db_session):
        """Test that delete_by_telegram_id removes account and cascaded data."""
        from tests.factories import create_active_therapy_session

        tid = 42345
        account = await create_account_with_prescreening(
            db_session,
            tid,
            patient_display_name="DeleteMe",
            mark_prescreening_complete=True,
        )
        # Create a session with messages to test cascade
        await create_active_therapy_session(db_session, account.id, flow_phase="therapy")

        acc_repo = AccountRepository(db_session)

        # Verify account exists before deletion
        before = await acc_repo.get_by_telegram_id(tid)
        assert before is not None
        assert before.user_profile is not None

        # Delete the account
        result = await acc_repo.delete_by_telegram_id(tid)
        assert result is True

        # Commit to flush deletions
        await db_session.commit()

        # Verify account is deleted
        after = await acc_repo.get_by_telegram_id(tid)
        assert after is None

    async def test_delete_by_telegram_id_returns_false_for_nonexistent(self, db_session):
        """Test that delete_by_telegram_id returns False for non-existent user."""
        acc_repo = AccountRepository(db_session)

        result = await acc_repo.delete_by_telegram_id(999999)
        assert result is False
