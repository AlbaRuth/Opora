"""Domain DTOs for sandbox orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ModelOverrides = dict[str, dict[str, dict[str, Any]]]


@dataclass(slots=True)
class PrescreeningProfile:
    """Prescreening data used by sandbox sessions."""

    patient_name: str = "Sandbox Пациент"
    patient_age: int | None = 32
    patient_sex: str = "prefer_not_to_say"
    address_mode: str = "formal"
    therapist_name: str = "Опора"
    therapist_gender: str = "female"
    therapist_styles: list[str] = field(default_factory=lambda: ["friendly"])


@dataclass(slots=True)
class SandboxSessionSpec:
    """Sandbox session creation data independent from HTTP schemas."""

    name: str = "Sandbox run"
    batch_id: int | None = None
    patient_template_id: int | None = None
    start_phase: str = "intake"
    prescreening_mode: str = "ai_generated"
    manual_prescreening_profile: PrescreeningProfile | None = None
    ai_prescreening_seed: str = ""
    scenario_seed: str = ""
    patient_persona_source: str = "generated"
    patient_name: str = "Sandbox Пациент"
    patient_age: int | None = 32
    patient_sex: str = "prefer_not_to_say"
    address_mode: str = "formal"
    model_overrides: ModelOverrides | None = None


@dataclass(slots=True)
class PatientTemplate:
    """Legacy reusable patient persona used by sandbox auto-run."""

    name: str
    persona: str
    presenting_problem: str
    hidden_facts: list[str] = field(default_factory=list)
    emotional_trajectory: str = ""
    cooperation_level: str = "neutral"
    safety_boundaries: list[str] = field(default_factory=list)
    max_turns: int = 8
    stop_conditions: list[str] = field(default_factory=list)
