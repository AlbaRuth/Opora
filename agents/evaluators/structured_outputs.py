"""Structured output helpers for evaluator and sandbox LLM tasks."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator


def extract_json_object(content: Any) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response without regex heuristics."""
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return {}

    text = content.strip()
    if not text:
        return {}

    candidates = [text]
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and first < last:
        candidates.append(text[first : last + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


class DialogueSignalResult(BaseModel):
    """Meaning-level patient signal analysis used by dialogue policy."""

    primary_emotion: str = ""
    emotional_intensity: float = Field(default=0.0, ge=0.0, le=1.0)
    crisis_signal: bool = False
    pushback_type: Literal["none", "stage", "hard_stop"] = "none"
    advice_request: bool = False
    question_stop: bool = False
    farewell_intent: bool = False
    active_style: str = "friendly"
    recommended_response_mode: Literal[
        "hold_space",
        "gentle_explore",
        "structured_gather",
    ] = "gentle_explore"
    question_guidance: Literal["encourage", "optional", "defer"] = "encourage"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale_short: str = ""

    @field_validator("active_style")
    @classmethod
    def normalize_style(cls, value: str) -> str:
        allowed = {"friendly", "soft", "business", "motivating"}
        normalized = (value or "").strip()
        return normalized if normalized in allowed else "friendly"


class ResponseStrategyResult(BaseModel):
    strategy: str = ""
    strategy_text: str = ""


class EmotionAssessmentResult(BaseModel):
    primary_emotion: str = ""
    emotional_intensity: float = Field(default=0.0, ge=0.0, le=1.0)


class TherapyProgressResult(BaseModel):
    new_therapy: str = "cognitive-behavioral therapy"
    reason: str = "maintain the original therapy"


class SandboxPrescreeningProfile(BaseModel):
    patient_name: str = "Sandbox Пациент"
    patient_age: int | None = Field(default=32, ge=13, le=120)
    patient_sex: Literal["male", "female", "prefer_not_to_say"] = "prefer_not_to_say"
    address_mode: Literal["formal", "informal"] = "formal"
    therapist_name: str = "Опора"
    therapist_gender: Literal["female", "male"] = "female"
    therapist_styles: list[str] = Field(default_factory=lambda: ["friendly"])
    scenario_brief: str = ""

    @field_validator("therapist_styles")
    @classmethod
    def normalize_styles(cls, value: list[str]) -> list[str]:
        allowed = {"friendly", "soft", "business", "motivating"}
        styles = [style for style in value if style in allowed]
        return styles or ["friendly"]


class SandboxScenario(BaseModel):
    persona_archetype: str = ""
    presenting_problem: str = ""
    mental_health_history: str = ""
    physical_health_history: str = ""
    current_problems: str = ""
    intake_hypothesis: str = ""
    intake_hypothesis_explanation: str = ""
    hidden_context: list[str] = Field(default_factory=list)
    emotional_arc: str = ""
    cooperation_style: str = ""
    speech_style: str = ""


class SandboxJudgeQualitySection(BaseModel):
    score: float = Field(default=0.0, ge=0.0, le=10.0)
    findings: list[str] = Field(default_factory=list)
    good_examples: list[str] = Field(default_factory=list)
    bad_examples: list[str] = Field(default_factory=list)


class SandboxJudgeExtractionQuality(BaseModel):
    score: float = Field(default=0.0, ge=0.0, le=10.0)
    findings: list[str] = Field(default_factory=list)
    missing_in_card: list[str] = Field(default_factory=list)
    hallucinated_in_card: list[str] = Field(default_factory=list)


class SandboxJudgeBottleneck(BaseModel):
    turn_number: int = 0
    component: Literal[
        "intake",
        "evaluator",
        "therapist",
        "auto_patient",
        "llm_gateway",
        "unknown",
    ] = "unknown"
    issue: str = ""
    evidence: str = ""
    severity: Literal["low", "medium", "high"] = "low"


class SandboxJudgeResult(BaseModel):
    overall_score: float = Field(default=0.0, ge=0.0, le=10.0)
    overall_verdict: Literal["pass", "needs_review", "fail"] = "needs_review"
    therapist_quality: SandboxJudgeQualitySection = Field(
        default_factory=SandboxJudgeQualitySection
    )
    extraction_quality: SandboxJudgeExtractionQuality = Field(
        default_factory=SandboxJudgeExtractionQuality
    )
    contextuality: dict[str, Any] = Field(default_factory=lambda: {"score": 0.0, "findings": []})
    psychologist_liveness: dict[str, Any] = Field(
        default_factory=lambda: {"score": 0.0, "findings": []}
    )
    architecture_bottlenecks: list[SandboxJudgeBottleneck] = Field(default_factory=list)
    latency_notes: list[str] = Field(default_factory=list)
    diversity_notes: list[str] = Field(default_factory=list)
    recommended_fixes: list[str] = Field(default_factory=list)


def validate_model(model_type: type[BaseModel], content: Any) -> BaseModel | None:
    """Validate extracted JSON against a pydantic model."""
    data = extract_json_object(content)
    if not data:
        return None
    try:
        return model_type.model_validate(data)
    except ValidationError:
        return None
