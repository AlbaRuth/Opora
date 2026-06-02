"""Domain DTOs for sandbox orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ModelOverrides = dict[str, dict[str, dict[str, Any]]]


@dataclass(slots=True)
class SandboxSessionSpec:
    """Sandbox session creation data independent from HTTP schemas."""

    name: str = "Sandbox run"
    patient_template_id: int | None = None
    patient_name: str = "Sandbox Пациент"
    patient_age: int | None = 32
    patient_sex: str = "prefer_not_to_say"
    address_mode: str = "formal"
    model_overrides: ModelOverrides | None = None


@dataclass(slots=True)
class PatientTemplate:
    """Versionable patient persona used by sandbox auto-run."""

    name: str
    persona: str
    presenting_problem: str
    hidden_facts: list[str] = field(default_factory=list)
    emotional_trajectory: str = ""
    cooperation_level: str = "neutral"
    safety_boundaries: list[str] = field(default_factory=list)
    max_turns: int = 8
    stop_conditions: list[str] = field(default_factory=list)
