"""Pydantic schemas for monitor API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    channel: str = "telegram"
    trace_id: str | None = None
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
    sandbox_run_id: int | None = None
    sandbox_batch_id: int | None = None
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
    prompt_messages_full: list[dict[str, Any]] | None = None
    response: str | None = None
    response_full: str | None = None
    prompt_truncated: bool = False
    response_truncated: bool = False
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
    channel: str | None = None
    source: str | None = None
    sandbox_run_id: int | None = None
    sandbox_batch_id: int | None = None
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


class SandboxBatchCreate(BaseModel):
    name: str = "Sandbox batch"
    count: int = Field(default=20, ge=1, le=100)
    parallelism: int = Field(default=5, ge=1, le=20)
    max_turns_per_run: int = Field(default=12, ge=1, le=20)
    start_phase: str = Field(default="prescreening", pattern="^(prescreening|intake|therapy)$")
    prescreening_mode: str = Field(default="ai_generated", pattern="^(manual|ai_generated)$")
    patient_persona_source: str = Field(default="generated", pattern="^(generated|manual|legacy_template)$")
    seed: str = ""
    model_overrides: ModelOverrides | None = None


class SandboxBatchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    batch_id: int
    name: str
    status: str
    requested_count: int
    parallelism: int
    max_turns_per_run: int
    created_runs: int = 0
    llm_model_config: dict[str, Any] | None = Field(default=None, alias="model_config")
    metadata: dict[str, Any] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stop_reason: str | None = None


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
    batch_id: int | None = None
    judge_result: dict[str, Any] | None = None


class SandboxTurnResponse(BaseModel):
    run_id: int
    trace_id: str | None
    patient_message: str
    assistant_message: str
    latency_ms: int | None = None
    metadata: dict[str, Any] | None = None
    stop_reason: str | None = None
    patient_trace_id: str | None = None
    intake_completed: bool = False
    closure_segments: dict[str, Any] | None = None


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


class ClinicalCardResponse(BaseModel):
    session_id: int
    account_id: int
    display_name: str | None = None
    age: str | None = None
    sex_display: str | None = None
    has_data: bool = False
    initial_info_insufficient: bool = False
    fields: dict[str, str] = Field(default_factory=dict)
    summary_text: str | None = None
