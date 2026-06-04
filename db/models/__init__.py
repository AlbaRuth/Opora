"""Database models for Opora.

New schema organization:
- identity: accounts (root entity)
- profile: user_profiles, therapist_preferences (user preferences)
- clinical: clinical_profiles (medical data)
- therapy: therapy_sessions, intake_states, messages, decision_logs
- observability: agent_logs, conversation_traces
"""

from .base import Base, TimestampMixin

# Identity schema
from .account import Account

# Profile schema
from .user_profile import UserProfile
from .therapist_preference import TherapistPreference
from .prescreening_state import PrescreeningState

# Clinical schema
from .clinical_profile import ClinicalProfile

# Therapy schema
from .therapy_session import TherapySession
from .intake_state import IntakeState
from .message import Message
from .decision_log import DecisionLog

# Observability schema
from .agent_log import AgentLog
from .conversation_trace import ConversationTrace

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    # Identity
    "Account",
    # Profile
    "UserProfile",
    "TherapistPreference",
    "PrescreeningState",
    # Clinical
    "ClinicalProfile",
    # Therapy
    "TherapySession",
    "IntakeState",
    "Message",
    "DecisionLog",
    # Observability
    "AgentLog",
    "ConversationTrace",
]
