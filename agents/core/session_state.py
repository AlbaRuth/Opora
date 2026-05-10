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
