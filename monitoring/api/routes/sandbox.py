"""Sandbox endpoints for Opora Monitor."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_config import get_llm_config_resolver
from db.repositories import (
    AgentLogRepository,
    PatientTemplateRepository,
    SandboxBatchRepository,
    SandboxRunRepository,
    SandboxTurnRepository,
)
from monitoring.api.deps import db_session, require_monitor_auth
from monitoring.api.schemas import (
    PatientTemplateResponse,
    SandboxAutoRunRequest,
    SandboxBatchCreate,
    SandboxBatchResponse,
    SandboxMessageRequest,
    SandboxSessionCreate,
    SandboxSessionResponse,
    SandboxTurnResponse,
)
from monitoring.sandbox.domain import PrescreeningProfile, SandboxSessionSpec
from monitoring.sandbox.runner import SandboxRunner

router = APIRouter(
    prefix="/api/sandbox",
    tags=["sandbox"],
    dependencies=[Depends(require_monitor_auth)],
)


def get_runner() -> SandboxRunner:
    return SandboxRunner()


def _sandbox_turn_response(run_id: int, turn) -> SandboxTurnResponse:
    metadata = turn.turn_metadata or {}
    return SandboxTurnResponse(
        run_id=run_id,
        trace_id=turn.trace_id,
        patient_message=turn.patient_message,
        assistant_message=turn.assistant_message,
        latency_ms=turn.latency_ms,
        metadata=metadata,
        stop_reason=turn.stop_reason,
        patient_trace_id=metadata.get("patient_trace_id"),
        intake_completed=bool(metadata.get("intake_completed")),
        closure_segments=metadata.get("closure_segments"),
    )


@router.post("/sessions", response_model=SandboxSessionResponse)
async def create_sandbox_session(
    request: SandboxSessionCreate,
    runner: SandboxRunner = Depends(get_runner),
) -> SandboxSessionResponse:
    run = await runner.create_session(
        SandboxSessionSpec(
            name=request.name,
            patient_template_id=request.patient_template_id,
            start_phase=request.start_phase,
            prescreening_mode=request.prescreening_mode,
            manual_prescreening_profile=(
                PrescreeningProfile(**request.manual_prescreening_profile.model_dump())
                if request.manual_prescreening_profile
                else None
            ),
            ai_prescreening_seed=request.ai_prescreening_seed,
            scenario_seed=request.scenario_seed,
            patient_persona_source=request.patient_persona_source,
            patient_name=request.patient_name,
            patient_age=request.patient_age,
            patient_sex=request.patient_sex,
            address_mode=request.address_mode,
            model_overrides=request.model_overrides,
        )
    )
    metadata = run.run_metadata or {}
    return SandboxSessionResponse(
        run_id=run.id,
        account_id=run.account_id,
        session_id=run.session_id,
        status=run.status,
        start_phase=metadata.get("start_phase"),
        prescreening_mode=metadata.get("prescreening_mode"),
        generated_prescreening_profile=metadata.get("generated_prescreening_profile"),
        generated_scenario=metadata.get("generated_scenario"),
        effective_model_config=run.model_config,
        batch_id=run.batch_id,
        judge_result=metadata.get("judge_result"),
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
    return _sandbox_turn_response(run_id, turn)


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
    return [_sandbox_turn_response(run_id, turn) for turn in turns]


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
        start_phase=(run.run_metadata or {}).get("start_phase"),
        prescreening_mode=(run.run_metadata or {}).get("prescreening_mode"),
        generated_prescreening_profile=(run.run_metadata or {}).get("generated_prescreening_profile"),
        generated_scenario=(run.run_metadata or {}).get("generated_scenario"),
        effective_model_config=run.model_config,
        batch_id=run.batch_id,
        judge_result=(run.run_metadata or {}).get("judge_result"),
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


@router.post("/sessions/{run_id}/judge", response_model=SandboxSessionResponse)
async def judge_sandbox_session(
    run_id: int,
    runner: SandboxRunner = Depends(get_runner),
    session: AsyncSession = Depends(db_session),
) -> SandboxSessionResponse:
    try:
        await runner.maybe_judge_run(run_id, force=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run = await SandboxRunRepository(session).get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Sandbox run not found")
    return SandboxSessionResponse(
        run_id=run.id,
        account_id=run.account_id,
        session_id=run.session_id,
        status=run.status,
        start_phase=(run.run_metadata or {}).get("start_phase"),
        prescreening_mode=(run.run_metadata or {}).get("prescreening_mode"),
        generated_prescreening_profile=(run.run_metadata or {}).get("generated_prescreening_profile"),
        generated_scenario=(run.run_metadata or {}).get("generated_scenario"),
        effective_model_config=run.model_config,
        batch_id=run.batch_id,
        judge_result=(run.run_metadata or {}).get("judge_result"),
    )


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
        start_phase=(run.run_metadata or {}).get("start_phase"),
        prescreening_mode=(run.run_metadata or {}).get("prescreening_mode"),
        generated_prescreening_profile=(run.run_metadata or {}).get("generated_prescreening_profile"),
        generated_scenario=(run.run_metadata or {}).get("generated_scenario"),
        effective_model_config=run.model_config,
        batch_id=run.batch_id,
        judge_result=(run.run_metadata or {}).get("judge_result"),
    )


@router.post("/batches", response_model=SandboxBatchResponse)
async def create_sandbox_batch(
    request: SandboxBatchCreate,
    session: AsyncSession = Depends(db_session),
    runner: SandboxRunner = Depends(get_runner),
) -> SandboxBatchResponse:
    batch = await runner.run_batch(
        name=request.name,
        count=request.count,
        parallelism=request.parallelism,
        max_turns_per_run=request.max_turns_per_run,
        start_phase=request.start_phase,
        prescreening_mode=request.prescreening_mode,
        patient_persona_source=request.patient_persona_source,
        seed=request.seed,
        model_overrides=request.model_overrides,
    )
    if not batch:
        raise HTTPException(status_code=500, detail="Sandbox batch was not created")
    runs = await SandboxRunRepository(session).list_for_batch(batch.id)
    return _batch_to_response(batch, created_runs=len(runs))


@router.get("/batches/{batch_id}", response_model=SandboxBatchResponse)
async def get_sandbox_batch(
    batch_id: int,
    session: AsyncSession = Depends(db_session),
) -> SandboxBatchResponse:
    batch = await SandboxBatchRepository(session).get_by_id(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Sandbox batch not found")
    runs = await SandboxRunRepository(session).list_for_batch(batch_id)
    return _batch_to_response(batch, created_runs=len(runs))


@router.get("/batches/{batch_id}/runs", response_model=list[SandboxSessionResponse])
async def list_sandbox_batch_runs(
    batch_id: int,
    session: AsyncSession = Depends(db_session),
) -> list[SandboxSessionResponse]:
    batch = await SandboxBatchRepository(session).get_by_id(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Sandbox batch not found")
    runs = await SandboxRunRepository(session).list_for_batch(batch_id)
    return [
        SandboxSessionResponse(
            run_id=run.id,
            account_id=run.account_id,
            session_id=run.session_id,
            status=run.status,
            start_phase=(run.run_metadata or {}).get("start_phase"),
            prescreening_mode=(run.run_metadata or {}).get("prescreening_mode"),
            generated_prescreening_profile=(run.run_metadata or {}).get("generated_prescreening_profile"),
            generated_scenario=(run.run_metadata or {}).get("generated_scenario"),
            effective_model_config=run.model_config,
            batch_id=run.batch_id,
            judge_result=(run.run_metadata or {}).get("judge_result"),
        )
        for run in runs
    ]


@router.get("/sessions/{run_id}/turns", response_model=list[SandboxTurnResponse])
async def list_sandbox_turns(
    run_id: int,
    session: AsyncSession = Depends(db_session),
) -> list[SandboxTurnResponse]:
    turns = await SandboxTurnRepository(session).list_for_run(run_id)
    return [_sandbox_turn_response(run_id, turn) for turn in turns]


@router.get("/sessions/{run_id}/export")
async def export_sandbox_run(
    run_id: int,
    format: str = Query(default="json", pattern="^(json|md)$"),
    session: AsyncSession = Depends(db_session),
):
    payload = await _sandbox_run_export_payload(run_id, session)
    if format == "json":
        return payload
    return Response(
        content=_sandbox_export_markdown(payload),
        media_type="text/markdown; charset=utf-8",
    )


@router.get("/batches/{batch_id}/export")
async def export_sandbox_batch(
    batch_id: int,
    format: str = Query(default="json", pattern="^(json|md)$"),
    session: AsyncSession = Depends(db_session),
):
    batch = await SandboxBatchRepository(session).get_by_id(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Sandbox batch not found")
    runs = await SandboxRunRepository(session).list_for_batch(batch_id)
    payload = {
        "batch": _batch_to_response(batch, created_runs=len(runs)).model_dump(mode="json"),
        "runs": [await _sandbox_run_export_payload(run.id, session) for run in runs],
    }
    if format == "json":
        return payload
    lines = [f"# Sandbox batch export: {batch.name}", ""]
    for run_payload in payload["runs"]:
        lines.append(_sandbox_export_markdown(run_payload))
        lines.append("")
    return Response(content="\n".join(lines), media_type="text/markdown; charset=utf-8")


def _batch_to_response(batch, *, created_runs: int) -> SandboxBatchResponse:
    return SandboxBatchResponse(
        batch_id=batch.id,
        name=batch.name,
        status=batch.status,
        requested_count=batch.requested_count,
        parallelism=batch.parallelism,
        max_turns_per_run=batch.max_turns_per_run,
        created_runs=created_runs,
        llm_model_config=batch.model_config,
        metadata=batch.batch_metadata,
        started_at=batch.started_at,
        finished_at=batch.finished_at,
        stop_reason=batch.stop_reason,
    )


async def _sandbox_run_export_payload(run_id: int, session: AsyncSession) -> dict:
    run = await SandboxRunRepository(session).get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Sandbox run not found")
    turns = await SandboxTurnRepository(session).list_for_run(run_id)
    log_repo = AgentLogRepository(session)
    session_logs = await log_repo.get_session_logs(run.session_id)
    llm_calls = [
        _log_to_export(log)
        for log in session_logs
        if log.sandbox_run_id == run.id
    ]
    return {
        "run": {
            "run_id": run.id,
            "batch_id": run.batch_id,
            "account_id": run.account_id,
            "session_id": run.session_id,
            "status": run.status,
            "model_config": run.model_config,
            "metadata": run.run_metadata,
        },
        "turns": [
            {
                "turn_number": turn.turn_number,
                "trace_id": str(turn.trace_id) if turn.trace_id else None,
                "patient_message": turn.patient_message,
                "assistant_message": turn.assistant_message,
                "latency_ms": turn.latency_ms,
                "metadata": turn.turn_metadata,
            }
            for turn in turns
        ],
        "judge_result": (run.run_metadata or {}).get("judge_result"),
        "llm_calls": llm_calls,
    }


def _log_to_export(log) -> dict:
    return {
        "id": log.id,
        "trace_id": str(log.trace_id) if log.trace_id else None,
        "channel": log.channel,
        "source": log.source,
        "sandbox_run_id": log.sandbox_run_id,
        "sandbox_batch_id": log.sandbox_batch_id,
        "agent_type": log.agent_type,
        "task_name": log.task_name,
        "model": log.model,
        "prompt_messages": log.prompt_messages_full or log.prompt_messages,
        "response": log.response_full or log.response,
        "latency_ms": log.latency_ms,
        "tokens_input": log.tokens_input,
        "tokens_output": log.tokens_output,
        "success": log.success,
        "error_message": log.error_message,
        "metadata": log.extra_metadata,
        "provider_metadata": log.provider_metadata,
        "created_at": log.created_at.isoformat(),
    }


def _sandbox_export_markdown(payload: dict) -> str:
    run = payload["run"]
    lines = [
        f"# Sandbox run export: {run['run_id']}",
        "",
        f"- batch_id: {run.get('batch_id')}",
        f"- session_id: {run['session_id']}",
        f"- status: {run['status']}",
        "",
        "## Transcript",
    ]
    for turn in payload["turns"]:
        lines.extend(
            [
                "",
                f"### Turn {turn['turn_number']}",
                f"Patient: {turn['patient_message']}",
                "",
                f"Psychologist: {turn['assistant_message']}",
            ]
        )
    judge = payload.get("judge_result") or {}
    lines.extend(["", "## QA Judge"])
    if not judge:
        lines.append("_Оценка не запускалась._")
    else:
        verdict = judge.get("overall_verdict", "—")
        score = judge.get("overall_score", "—")
        lines.extend([f"- **Verdict:** {verdict}", f"- **Overall score:** {score}", ""])
        therapist = judge.get("therapist_quality") or {}
        extraction = judge.get("extraction_quality") or {}
        lines.extend(
            [
                f"### Therapist quality ({therapist.get('score', '—')}/10)",
                "",
            ]
        )
        for finding in therapist.get("findings") or []:
            lines.append(f"- {finding}")
        lines.extend(
            [
                "",
                f"### Extraction quality ({extraction.get('score', '—')}/10)",
                "",
            ]
        )
        for finding in extraction.get("findings") or []:
            lines.append(f"- {finding}")
        missing = extraction.get("missing_in_card") or []
        if missing:
            lines.extend(["", "**Missing in card:**"])
            for item in missing:
                lines.append(f"- {item}")
        hallucinated = extraction.get("hallucinated_in_card") or []
        if hallucinated:
            lines.extend(["", "**Hallucinated in card:**"])
            for item in hallucinated:
                lines.append(f"- {item}")
        bottlenecks = judge.get("architecture_bottlenecks") or []
        if bottlenecks:
            lines.extend(["", "### Architecture bottlenecks", ""])
            for item in bottlenecks:
                lines.append(
                    f"- Turn {item.get('turn_number')}: [{item.get('severity')}] "
                    f"{item.get('component')} — {item.get('issue')}"
                )
        fixes = judge.get("recommended_fixes") or []
        if fixes:
            lines.extend(["", "### Recommended fixes", ""])
            for fix in fixes:
                lines.append(f"- {fix}")
    lines.extend(["", "## LLM Calls"])
    for call in payload["llm_calls"]:
        lines.extend(
            [
                "",
                f"### {call['agent_type']}.{call['task_name']}",
                f"- source: {call.get('channel')}/{call.get('source')}",
                f"- model: {call['model']}",
                f"- latency_ms: {call.get('latency_ms')}",
            ]
        )
    return "\n".join(lines)
