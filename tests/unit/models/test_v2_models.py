"""Unit tests for v2 schema models (identity/profile/clinical)."""

from datetime import datetime

from db.models import Account, ClinicalProfile, TherapistPreference, UserProfile


class TestTherapistPreferencePrescreening:
    def test_is_prescreening_complete_true(self):
        pref = TherapistPreference(
            account_id=1,
            prescreening_completed_at=datetime.utcnow(),
            therapist_name="Опора",
            therapist_gender="female",
        )
        assert pref.is_prescreening_complete is True

    def test_is_prescreening_complete_false(self):
        pref = TherapistPreference(
            account_id=1,
            prescreening_completed_at=None,
            therapist_name="Опора",
            therapist_gender="female",
        )
        assert pref.is_prescreening_complete is False

    def test_get_therapist_profile(self):
        """Test that get_therapist_profile returns styles (stored in therapist_traits field)."""
        pref = TherapistPreference(
            account_id=1,
            therapist_name="Доктор Анна",
            therapist_gender="female",
            therapist_traits=["friendly", "soft"],  # Field still called therapist_traits in DB
        )
        profile = pref.get_therapist_profile()
        assert profile["name"] == "Доктор Анна"
        assert profile["gender"] == "female"
        assert profile["styles"] == ["friendly", "soft"]  # NEW: returns styles key

    def test_construct_with_defaults(self):
        """ORM defaults are applied on INSERT; explicit values for unit checks."""
        pref = TherapistPreference(
            account_id=1,
            therapist_name="Опора",
            therapist_gender="female",
        )
        assert pref.therapist_name == "Опора"
        assert pref.therapist_gender == "female"


class TestUserProfileDisplay:
    def test_effective_display_name_chain(self):
        acc = Account(telegram_id=1, first_name="TelegramName")
        up = UserProfile(account_id=1, display_name=None, legacy_pseudonym=None)
        up.account = acc
        assert up.effective_display_name == "TelegramName"

    def test_effective_display_name_fallback_patient(self):
        acc = Account(telegram_id=2, first_name=None)
        up = UserProfile(account_id=2, display_name=None, legacy_pseudonym=None)
        up.account = acc
        assert up.effective_display_name == "Пациент"

    def test_effective_age(self):
        up = UserProfile(account_id=1, age=30)
        assert up.effective_age == "30"


class TestClinicalProfileRecord:
    def test_get_patient_record(self):
        acc = Account(telegram_id=3, first_name="n")
        up = UserProfile(account_id=3, display_name="Иван", age=30, sex="male")
        up.account = acc
        acc.user_profile = up
        cp = ClinicalProfile(
            account_id=3,
            mental_health_history="mh",
            physical_health_history="ph",
            current_problems="cp",
            intake_hypothesis="ih",
            intake_hypothesis_explanation="ihe",
        )
        cp.account = acc
        record = cp.get_patient_record()
        assert record["patient_pseudonym"] == "Иван"
        assert record["patient_age"] == "30"
        assert record["patient_sex"] == "male"
        assert record["current_problems"] == "cp"

    def test_is_card_filled(self):
        cp = ClinicalProfile(account_id=1, current_problems="x")
        assert cp.is_card_filled() is True

    def test_is_card_filled_whitespace_only(self):
        cp = ClinicalProfile(account_id=1, mental_health_history="   \n")
        assert cp.is_card_filled() is False
