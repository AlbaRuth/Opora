"""
Unit tests for SessionState with prescreening profile fields.
"""

import pytest

from agents.core import SessionState


class TestSessionStateProfile:
    """Test SessionState with prescreening profile fields."""

    def test_session_state_with_defaults(self):
        """Test SessionState with default profile values."""
        state = SessionState(
            patient_id="123",
            session_id="123_1",
            session_db_id=1,
            dialog_count=0,
            session_counter=1,
        )

        assert state.therapist_name == "Опора"
        assert state.therapist_gender == "female"
        assert state.therapist_traits == []
        assert state.patient_display_name == ""
        assert state.patient_age is None

    def test_session_state_with_custom_profile(self):
        """Test SessionState with custom profile values."""
        state = SessionState(
            patient_id="123",
            session_id="123_1",
            session_db_id=1,
            dialog_count=0,
            session_counter=1,
            therapist_name="Доктор Анна",
            therapist_gender="female",
            therapist_traits=["calm", "empathetic"],
            patient_display_name="Иван",
            patient_age=30,
        )

        assert state.therapist_name == "Доктор Анна"
        assert state.therapist_gender == "female"
        assert state.therapist_traits == ["calm", "empathetic"]
        assert state.patient_display_name == "Иван"
        assert state.patient_age == 30

    def test_session_state_slots(self):
        """Test SessionState uses slots correctly."""
        state = SessionState(
            patient_id="123",
            session_id="123_1",
            session_db_id=1,
            dialog_count=0,
            session_counter=1,
        )

        # Should not allow setting arbitrary attributes
        with pytest.raises(AttributeError):
            state.arbitrary_attribute = "value"

    def test_session_state_immutable_fields(self):
        """Test that profile fields can be modified after creation."""
        state = SessionState(
            patient_id="123",
            session_id="123_1",
            session_db_id=1,
            dialog_count=0,
            session_counter=1,
            therapist_name="Опора",
        )

        # Should allow modification
        state.therapist_name = "НовоеИмя"
        assert state.therapist_name == "НовоеИмя"
