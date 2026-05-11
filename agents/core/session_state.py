"""
Session state DTOs for stateless therapist orchestration.
"""

from dataclasses import dataclass, field


@dataclass(slots=True)
class SessionState:
    """Explicit per-session state passed through orchestration calls."""

    patient_id: str
    session_id: str
    session_db_id: int | None
    dialog_count: int
    session_counter: int
    current_therapy: str = "unspecified therapy"
    current_stage: str = ""
    flow_phase: str = "therapy"
    intake_user_turns: int = 0

    # User profile from prescreening
    therapist_name: str = "Опора"
    therapist_gender: str = "female"
    therapist_traits: list[str] = field(default_factory=list)
    patient_display_name: str = ""
    patient_age: int | None = None
    # NEW: Patient sex for personalized responses
    patient_sex: str = "prefer_not_to_say"
    # NEW: Address mode for controlling formal/informal tone (ты/вы)
    address_mode: str = "formal"

    @property
    def is_formal_address(self) -> bool:
        """Check if formal address mode (вы) is preferred."""
        return self.address_mode == "formal"

    @property
    def is_informal_address(self) -> bool:
        """Check if informal address mode (ты) is preferred."""
        return self.address_mode == "informal"

    def get_address_pronoun_you(self) -> str:
        """Get the appropriate 'you' pronoun for Russian."""
        return "вы" if self.is_formal_address else "ты"

    def get_address_pronoun_your(self) -> str:
        """Get the appropriate 'your' pronoun for Russian."""
        return "ваш" if self.is_formal_address else "твой"

    def get_address_verb_suffix(self, verb_root: str = "") -> str:
        """Get appropriate verb suffix for Russian based on address mode."""
        # This is a simplified helper - full Russian conjugation is complex
        # Used primarily for common phrases like "хотите/хочешь"
        if self.is_formal_address:
            return "ите"  # formal suffix
        return "и"  # informal suffix
