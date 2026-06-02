"""SessionState construction helpers."""

from __future__ import annotations

from agents.core.session_state import SessionState
from services.user_context import UserContext


def build_session_state(
    *,
    context: UserContext,
    session_number: int,
    session_db_id: int,
    dialog_count: int = 0,
    current_therapy: str = "unspecified therapy",
    current_stage: str = "",
    flow_phase: str = "therapy",
    intake_user_turns: int = 0,
) -> SessionState:
    """Single canonical SessionState factory."""
    return SessionState(
        patient_id=str(context.account_id),
        session_id=f"{context.account_id}_{session_number}",
        session_db_id=session_db_id,
        dialog_count=dialog_count,
        session_counter=session_number,
        current_therapy=current_therapy,
        current_stage=current_stage,
        flow_phase=flow_phase,  # type: ignore[arg-type]
        intake_user_turns=intake_user_turns,
        therapist_name=context.therapist_name,
        therapist_gender=context.therapist_gender,  # type: ignore[arg-type]
        therapist_styles=context.therapist_styles,
        patient_display_name=context.patient_display_name,
        patient_age=context.patient_age,
        patient_sex=context.patient_sex,  # type: ignore[arg-type]
        address_mode=context.address_mode,  # type: ignore[arg-type]
    )

