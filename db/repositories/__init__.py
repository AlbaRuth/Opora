"""Database repositories for Opora.

New schema organization:
- AccountRepository - identity.accounts operations
- UserProfileRepository - profile.user_profiles operations (NEW: sex, address_mode)
- TherapistPreferenceRepository - profile.therapist_preferences operations
- ClinicalProfileRepository - clinical.clinical_profiles operations
- SessionRepository - therapy.therapy_sessions operations
- IntakeStateRepository - therapy.intake_states operations
- MessageRepository - therapy.messages operations
- DecisionLogRepository - therapy.decision_logs operations
- AgentLogRepository - observability.agent_logs operations
"""

from .base import BaseRepository

# New schema repositories
from .account import AccountRepository
from .user_profile import UserProfileRepository
from .therapist_preference import TherapistPreferenceRepository
from .prescreening_state import PrescreeningStateRepository
from .clinical_profile import ClinicalProfileRepository
from .session import SessionRepository
from .intake_state import IntakeStateRepository
from .message import MessageRepository
from .decision import DecisionLogRepository
from .agent_log import AgentLogRepository
from .conversation_trace import ConversationTraceRepository
from .sandbox import PatientTemplateRepository, SandboxRunRepository, SandboxTurnRepository

__all__ = [
    # Base
    "BaseRepository",
    # New schema
    "AccountRepository",
    "UserProfileRepository",
    "TherapistPreferenceRepository",
    "PrescreeningStateRepository",
    "ClinicalProfileRepository",
    "SessionRepository",
    "IntakeStateRepository",
    "MessageRepository",
    "DecisionLogRepository",
    "AgentLogRepository",
    "ConversationTraceRepository",
    "PatientTemplateRepository",
    "SandboxRunRepository",
    "SandboxTurnRepository",
]
