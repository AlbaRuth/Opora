"""Sandbox endpoints for Opora Monitor."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_config import get_llm_config_resolver
from db.repositories import PatientTemplateRepository, SandboxRunRepository, SandboxTurnRepository
from monitoring.api.deps import db_session, require_monitor_auth
from monitoring.api.schemas import (
    PatientTemplateResponse,
    SandboxAutoRunRequest,
    SandboxMessageRequest,
    SandboxSessionCreate,
    SandboxSessionResponse,
    SandboxTurnResponse,
)
from monitoring.sandbox.domain import SandboxSessionSpec
from monitoring.sandbox.runner import SandboxRunner

router = APIRouter(
    prefix="/api/sandbox",
    tags=["sandbox"],
    dependencies=[Depends(require_monitor_auth)],
)


def get_runner() -> SandboxRunner:
    return SandboxRunner()


@router.post("/sessions", response_model=SandboxSessionResponse)
async def create_sandbox_session(
    request: SandboxSessionCreate,
    runner: SandboxRunner = Depends(get_runner),
) -> SandboxSessionResponse:
    run = await runner.create_session(
        SandboxSessionSpec(
            name=request.name,
            patient_template_id=request.patient_template_id,
            patient_name=request.patient_name,
            patient_age=request.patient_age,
            patient_sex=request.patient_sex,
            address_mode=request.address_mode,
            model_overrides=request.model_overrides,
        )
    )
    return SandboxSessionResponse(
        run_id=run.id,
        account_id=run.account_id,
        session_id=run.session_id,
        status=run.status,
        effective_model_config=run.model_config,
    )


@router.post("/sessions/{run_id}/messages", response_model=SandboxTurnResponse)
async def send_sandbox_message(
    run_id: int,
    request: SandboxMessageRequest,
    runner: SandboxRunner = Depends(get_runner),
) -> SandboxTurnResponse:
    try:
        turn = await runner.send_message(
            run_id,
            request.message,
            model_overrides=request.model_overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SandboxTurnResponse(
        run_id=run_id,
        trace_id=turn.trace_id,
        patient_message=turn.patient_message,
        assistant_message=turn.assistant_message,
        latency_ms=turn.latency_ms,
        metadata=turn.turn_metadata,
    )


@router.post("/sessions/{run_id}/auto-run", response_model=list[SandboxTurnResponse])
async def auto_run_sandbox(
    run_id: int,
    request: SandboxAutoRunRequest,
    runner: SandboxRunner = Depends(get_runner),
) -> list[SandboxTurnResponse]:
    try:
        turns = await runner.auto_run(
            run_id,
            request.max_turns,
            model_overrides=request.model_overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        SandboxTurnResponse(
            run_id=run_id,
            trace_id=turn.trace_id,
            patient_message=turn.patient_message,
            assistant_message=turn.assistant_message,
            latency_ms=turn.latency_ms,
            metadata=turn.turn_metadata,
        )
        for turn in turns
    ]


@router.post("/sessions/{run_id}/stop", response_model=SandboxSessionResponse)
async def stop_sandbox_session(
    run_id: int,
    runner: SandboxRunner = Depends(get_runner),
) -> SandboxSessionResponse:
    run = await runner.stop(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Sandbox run not found")
    return SandboxSessionResponse(
        run_id=run.id,
        account_id=run.account_id,
        session_id=run.session_id,
        status=run.status,
        effective_model_config=run.model_config,
    )


@router.get("/templates/patients", response_model=list[PatientTemplateResponse])
async def list_patient_templates(
    session: AsyncSession = Depends(db_session),
) -> list[PatientTemplateResponse]:
    repo = PatientTemplateRepository(session)
    templates = await repo.list_active()
    if not templates:
        templates = [await repo.ensure_default()]
    return [
        PatientTemplateResponse(
            id=template.id,
            name=template.name,
            version=template.version,
            persona=template.persona,
            presenting_problem=template.presenting_problem,
            hidden_facts=template.hidden_facts or [],
            emotional_trajectory=template.emotional_trajectory,
            cooperation_level=template.cooperation_level,
            safety_boundaries=template.safety_boundaries or [],
            max_turns=template.max_turns,
            stop_conditions=template.stop_conditions or [],
        )
        for template in templates
    ]


@router.get("/model-config")
async def get_default_model_config() -> dict:
    return get_llm_config_resolver().effective_config()


@router.get("/sessions/{run_id}", response_model=SandboxSessionResponse)
async def get_sandbox_session(
    run_id: int,
    session: AsyncSession = Depends(db_session),
) -> SandboxSessionResponse:
    run = await SandboxRunRepository(session).get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Sandbox run not found")
    return SandboxSessionResponse(
        run_id=run.id,
        account_id=run.account_id,
        session_id=run.session_id,
        status=run.status,
        effective_model_config=run.model_config,
    )


@router.get("/sessions/{run_id}/turns", response_model=list[SandboxTurnResponse])
async def list_sandbox_turns(
    run_id: int,
    session: AsyncSession = Depends(db_session),
) -> list[SandboxTurnResponse]:
    turns = await SandboxTurnRepository(session).list_for_run(run_id)
    return [
        SandboxTurnResponse(
            run_id=run_id,
            trace_id=turn.trace_id,
            patient_message=turn.patient_message,
            assistant_message=turn.assistant_message,
            latency_ms=turn.latency_ms,
            metadata=turn.turn_metadata,
        )
        for turn in turns
    ]
