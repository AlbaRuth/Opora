"""Pydantic schemas for monitor API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str = "opora-monitor"


class ChatSummary(BaseModel):
    session_id: int
    account_id: int
    telegram_id: int
    username: str | None = None
    display_name: str | None = None
    source: str
    session_number: int
    therapy_type: str
    is_active: bool
    dialog_count: int
    created_at: datetime
    updated_at: datetime


class MessageItem(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    message_number: int
    primary_emotion: str | None = None
    emotional_intensity: float | None = None
    created_at: datetime


class TraceSummary(BaseModel):
    trace_id: str
    turn_id: str
    session_id: int | None
    account_id: int | None
    channel: str
    source: str
    status: str
    duration_ms: int | None
    llm_latency_ms: int
    total_tokens_input: int
    total_tokens_output: int
    total_cost_usd: float | None = None
    started_at: datetime
    finished_at: datetime | None = None
    error_message: str | None = None


class LlmCallItem(BaseModel):
    id: int
    agent_type: str
    task_name: str
    model: str
    temperature: float
    max_tokens: int
    prompt: str | None = None
    prompt_messages: list[dict[str, Any]] | None = None
    response: str | None = None
    reasoning: str | None = None
    reasoning_summary: str | None = None
    latency_ms: int | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_usd: float | None = None
    success: bool
    error_message: str | None = None
    metadata: dict[str, Any] | None = None
    provider_metadata: dict[str, Any] | None = None
    created_at: datetime


class TraceDetail(BaseModel):
    trace: TraceSummary
    llm_calls: list[LlmCallItem]


ModelOverrides = dict[str, dict[str, dict[str, Any]]]


class SandboxPrescreeningProfileRequest(BaseModel):
    patient_name: str = "Sandbox Пациент"
    patient_age: int | None = Field(default=32, ge=13, le=120)
    patient_sex: str = "prefer_not_to_say"
    address_mode: str = "formal"
    therapist_name: str = "Опора"
    therapist_gender: str = "female"
    therapist_styles: list[str] = Field(default_factory=lambda: ["friendly"])


class SandboxSessionCreate(BaseModel):
    name: str = "Sandbox run"
    patient_template_id: int | None = None
    start_phase: str = Field(default="intake", pattern="^(prescreening|intake|therapy)$")
    prescreening_mode: str = Field(default="manual", pattern="^(manual|ai_generated)$")
    manual_prescreening_profile: SandboxPrescreeningProfileRequest | None = None
    ai_prescreening_seed: str = ""
    scenario_seed: str = ""
    patient_persona_source: str = Field(default="generated", pattern="^(generated|manual|legacy_template)$")
    patient_name: str = "Sandbox Пациент"
    patient_age: int | None = 32
    patient_sex: str = "prefer_not_to_say"
    address_mode: str = "formal"
    model_overrides: ModelOverrides | None = None


class SandboxMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    model_overrides: ModelOverrides | None = None


class SandboxAutoRunRequest(BaseModel):
    max_turns: int = Field(default=3, ge=1, le=20)
    model_overrides: ModelOverrides | None = None


class SandboxSessionResponse(BaseModel):
    run_id: int
    account_id: int
    session_id: int
    status: str
    start_phase: str | None = None
    prescreening_mode: str | None = None
    generated_prescreening_profile: dict[str, Any] | None = None
    generated_scenario: dict[str, Any] | None = None
    effective_model_config: dict[str, Any] | None = None


class SandboxTurnResponse(BaseModel):
    run_id: int
    trace_id: str | None
    patient_message: str
    assistant_message: str
    latency_ms: int | None = None
    metadata: dict[str, Any] | None = None


class PatientTemplateResponse(BaseModel):
    id: int
    name: str
    version: int
    persona: str
    presenting_problem: str
    hidden_facts: list[str]
    emotional_trajectory: str | None = None
    cooperation_level: str
    safety_boundaries: list[str]
    max_turns: int
    stop_conditions: list[str]
