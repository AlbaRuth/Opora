"""Unit tests for SessionState DTO."""

import sys
from pathlib import Path
import pytest

# Import directly from file to avoid circular import through agents/__init__.py
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root / "agents" / "core"))
from session_state import SessionState
sys.path.pop(0)


class TestSessionState:
    """Test SessionState dataclass behavior."""

    def test_session_state_creation(self):
        """Test basic SessionState creation with all fields."""
        state = SessionState(
            patient_id="123",
            session_id="123_1",
            session_db_id=1,
            dialog_count=5,
            session_counter=1,
            current_therapy="cognitive-behavioral therapy",
            current_stage="assessment",
        )

        assert state.patient_id == "123"
        assert state.session_id == "123_1"
        assert state.session_db_id == 1
        assert state.dialog_count == 5
        assert state.session_counter == 1
        assert state.current_therapy == "cognitive-behavioral therapy"
        assert state.current_stage == "assessment"

    def test_session_state_defaults(self):
        """Test SessionState with default values."""
        state = SessionState(
            patient_id="456",
            session_id="456_2",
            session_db_id=2,
            dialog_count=0,
            session_counter=2,
        )

        assert state.current_therapy == "unspecified therapy"
        assert state.current_stage == ""

    def test_session_state_mutation(self):
        """Test that SessionState fields can be mutated during processing."""
        state = SessionState(
            patient_id="789",
            session_id="789_1",
            session_db_id=3,
            dialog_count=0,
            session_counter=1,
        )

        # Simulate processing increments
        state.dialog_count += 1
        state.current_therapy = "psychodynamic therapy"
        state.current_stage = "working_through"

        assert state.dialog_count == 1
        assert state.current_therapy == "psychodynamic therapy"
        assert state.current_stage == "working_through"

    def test_session_state_from_db_mapping(self):
        """Test mapping from DB session to SessionState DTO."""
        # Simulated DB session data
        db_session_data = {
            "user_id": 100,
            "id": 50,
            "session_number": 3,
            "dialog_count": 10,
            "therapy_type": "mindfulness-based therapy",
            "current_stage": "maintenance",
        }

        state = SessionState(
            patient_id=str(db_session_data["user_id"]),
            session_id=f"{db_session_data['user_id']}_{db_session_data['session_number']}",
            session_db_id=db_session_data["id"],
            dialog_count=db_session_data["dialog_count"],
            session_counter=db_session_data["session_number"],
            current_therapy=db_session_data["therapy_type"],
            current_stage=db_session_data["current_stage"] or "",
        )

        assert state.patient_id == "100"
        assert state.session_id == "100_3"
        assert state.session_db_id == 50
        assert state.session_counter == 3


class TestSessionStateAddressMode:
    def test_formal_pronouns(self):
        state = SessionState(
            patient_id="1",
            session_id="1_1",
            session_db_id=1,
            dialog_count=0,
            session_counter=1,
            address_mode="formal",
        )
        assert state.get_address_pronoun_you() == "вы"
        assert state.get_address_pronoun_your() == "ваш"
        assert state.get_address_verb_suffix() == "ите"

    def test_informal_pronouns(self):
        state = SessionState(
            patient_id="1",
            session_id="1_1",
            session_db_id=1,
            dialog_count=0,
            session_counter=1,
            address_mode="informal",
        )
        assert state.get_address_pronoun_you() == "ты"
        assert state.get_address_pronoun_your() == "твой"
        assert state.get_address_verb_suffix() == "и"
