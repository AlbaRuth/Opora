"""
Unit tests for User model with prescreening functionality.
"""

import pytest
from datetime import datetime

from db.models import User


class TestUserModelPrescreening:
    """Test prescreening-related methods in User model."""

    def test_is_prescreening_complete_true(self):
        """Test is_prescreening_complete property when completed."""
        user = User(
            telegram_id=12345,
            prescreening_completed_at=datetime.utcnow(),
        )
        assert user.is_prescreening_complete is True

    def test_is_prescreening_complete_false(self):
        """Test is_prescreening_complete property when not completed."""
        user = User(
            telegram_id=12345,
            prescreening_completed_at=None,
        )
        assert user.is_prescreening_complete is False

    def test_get_patient_record_with_prescreening(self):
        """Test get_patient_record with prescreening fields."""
        user = User(
            telegram_id=12345,
            patient_display_name="Иван",
            patient_age=30,
            mental_health_history="Some history",
            physical_health_history="Good health",
            current_problems="Anxiety",
            intake_hypothesis="Preliminary anxiety hypothesis",
            intake_hypothesis_explanation="Symptoms linked to stress",
        )
        record = user.get_patient_record()

        assert record["patient_pseudonym"] == "Иван"
        assert record["patient_age"] == "30"
        assert record["mental_health_history"] == "Some history"
        assert record["physical_health_history"] == "Good health"
        assert record["current_problems"] == "Anxiety"
        assert record["intake_hypothesis"] == "Preliminary anxiety hypothesis"
        assert record["intake_hypothesis_explanation"] == "Symptoms linked to stress"

    def test_get_patient_record_fallback_to_legacy(self):
        """Test get_patient_record falls back to legacy fields."""
        user = User(
            telegram_id=12345,
            patient_pseudonym="СтарыйПсевдоним",
            patient_age_legacy="40",
        )
        record = user.get_patient_record()

        assert record["patient_pseudonym"] == "СтарыйПсевдоним"
        assert record["patient_age"] == "40"

    def test_get_patient_record_prescreening_priority(self):
        """Test that prescreening fields take priority over legacy."""
        user = User(
            telegram_id=12345,
            patient_pseudonym="СтарыйПсевдоним",
            patient_age_legacy="40",
            patient_display_name="НовоеИмя",
            patient_age=25,
        )
        record = user.get_patient_record()

        # Prescreening fields should take priority
        assert record["patient_pseudonym"] == "НовоеИмя"
        assert record["patient_age"] == "25"

    def test_get_patient_record_empty(self):
        """Test get_patient_record with empty fields."""
        user = User(
            telegram_id=12345,
        )
        record = user.get_patient_record()

        assert record["patient_pseudonym"] == ""
        assert record["patient_age"] == ""
        assert record["mental_health_history"] == ""
        assert record["physical_health_history"] == ""
        assert record["current_problems"] == ""
        assert record["intake_hypothesis"] == ""
        assert record["intake_hypothesis_explanation"] == ""

    def test_get_therapist_profile_with_defaults(self):
        """Test get_therapist_profile with default values."""
        user = User(
            telegram_id=12345,
        )
        profile = user.get_therapist_profile()

        assert profile["name"] == "Опора"
        assert profile["gender"] == "female"
        assert profile["traits"] == []

    def test_get_therapist_profile_custom(self):
        """Test get_therapist_profile with custom values."""
        user = User(
            telegram_id=12345,
            therapist_name="Доктор Анна",
            therapist_gender="female",
            therapist_traits=["calm", "empathetic"],
        )
        profile = user.get_therapist_profile()

        assert profile["name"] == "Доктор Анна"
        assert profile["gender"] == "female"
        assert profile["traits"] == ["calm", "empathetic"]

    def test_default_therapist_name(self):
        """Test default therapist_name is set."""
        user = User(telegram_id=12345)
        assert user.therapist_name == "Опора"

    def test_default_therapist_gender(self):
        """Test default therapist_gender is set."""
        user = User(telegram_id=12345)
        assert user.therapist_gender == "female"

    def test_default_therapist_traits(self):
        """Test default therapist_traits is empty list."""
        user = User(telegram_id=12345)
        assert user.therapist_traits == []
