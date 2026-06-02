"""Sandbox runner that exercises real dialogue services without Telegram."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from dataclasses import asdict
from uuid import uuid4

from sqlalchemy import select, update

from core.channels import CHANNEL_SANDBOX, SANDBOX_TELEGRAM_ID_BASE
from core.config import get_settings
from core.llm_config import get_llm_config_resolver, llm_overrides_scope
from db.models import Account, AgentLog, ConversationTrace, SandboxRun, SandboxTurn
from db.repositories import (
    AccountRepository,
    AgentLogRepository,
    ConversationTraceRepository,
    ClinicalProfileRepository,
    IntakeStateRepository,
    PatientTemplateRepository,
    SandboxBatchRepository,
    SandboxRunRepository,
    SandboxTurnRepository,
    SessionRepository,
    TherapistPreferenceRepository,
    UserProfileRepository,
)
from db.session import get_db_session
from monitoring.sandbox.auto_patient import AutoPatient
from monitoring.sandbox.domain import PrescreeningProfile, SandboxSessionSpec
from monitoring.sandbox.judge import SandboxJudge
from observability.tracing import TraceContext, trace_scope
from services.dialogue_service import DialogueService
from services.session_lifecycle import get_or_create_active_session


class SandboxRunner:
    """Create and drive synthetic chats through DialogueService."""

    def __init__(
        self,
        dialogue_service: DialogueService | None = None,
        auto_patient: AutoPatient | None = None,
        sandbox_judge: SandboxJudge | None = None,
    ) -> None:
        self.settings = get_settings()
        self.llm_config_resolver = get_llm_config_resolver()
        self.dialogue_service = dialogue_service or DialogueService()
        self.auto_patient = auto_patient or AutoPatient()
        self.sandbox_judge = sandbox_judge or SandboxJudge()

    async def create_session(self, request: SandboxSessionSpec) -> SandboxRun:
        telegram_id = self._new_sandbox_telegram_id()
        async with get_db_session() as session:
            account_repo = AccountRepository(session)
            template_repo = PatientTemplateRepository(session)
            run_repo = SandboxRunRepository(session)

            template = None
            if request.patient_persona_source == "legacy_template":
                template = (
                    await template_repo.get_by_id(request.patient_template_id)
                    if request.patient_template_id
                    else await template_repo.ensure_default()
                )
            initial_profile = request.manual_prescreening_profile or PrescreeningProfile(
                patient_name=request.patient_name,
                patient_age=request.patient_age,
                patient_sex=request.patient_sex,
                address_mode=request.address_mode,
            )
            account = await account_repo.create_from_telegram(
                telegram_id=telegram_id,
                username=f"sandbox_{telegram_id}",
                first_name=initial_profile.patient_name,
                language_code="ru",
                origin=CHANNEL_SANDBOX,
            )
            trace = TraceContext(channel="sandbox", source="sandbox_setup")
            trace.account_id = account.id
            trace.sandbox_batch_id = request.batch_id
            status = "success"
            error_message: str | None = None
            started = time.perf_counter()
            with trace_scope(trace):
                try:
                    profile, generated_profile = await self._resolve_prescreening_profile(
                        request,
                        account_id=account.id,
                    )
                    account.first_name = profile.patient_name
                    generated_scenario = await self._resolve_scenario(
                        request,
                        profile,
                        account_id=account.id,
                    )
                except Exception as exc:
                    status = "error"
                    error_message = str(exc)
                    raise
                finally:
                    await ConversationTraceRepository(session).create_from_context(
                        trace=trace,
                        status=status,
                        finished_at=datetime.now(timezone.utc),
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        error_message=error_message,
                    )
            await self._apply_prescreening_profile(
                session=session,
                account_id=account.id,
                profile=profile,
                mark_complete=request.start_phase != "prescreening",
            )
            if account.clinical_profile and request.start_phase == "therapy":
                if generated_scenario:
                    account.clinical_profile.mental_health_history = generated_scenario.mental_health_history
                    account.clinical_profile.physical_health_history = generated_scenario.physical_health_history
                    account.clinical_profile.current_problems = generated_scenario.current_problems
                    account.clinical_profile.intake_hypothesis = generated_scenario.intake_hypothesis
                    account.clinical_profile.intake_hypothesis_explanation = (
                        generated_scenario.intake_hypothesis_explanation
                    )
                elif template:
                    account.clinical_profile.current_problems = template.presenting_problem

            created = await get_or_create_active_session(
                account_id=account.id,
                intake_enabled=(request.start_phase != "therapy" and self.settings.intake_enabled),
                session=session,
            )
            if request.start_phase == "prescreening":
                intake_repo = IntakeStateRepository(session)
                intake_state = await intake_repo.get_by_session_id(created.session_id)
                if intake_state:
                    intake_state.flow_phase = "prescreening"
            run = await run_repo.create_run(
                account_id=account.id,
                session_id=created.session_id,
                batch_id=request.batch_id,
                patient_template_id=template.id if template else None,
                name=request.name,
                model_config=self.llm_config_resolver.effective_config(
                    overrides=request.model_overrides,
                ),
                metadata={
                    "channel": "sandbox",
                    "model_overrides": request.model_overrides,
                    "start_phase": request.start_phase,
                    "prescreening_mode": request.prescreening_mode,
                    "manual_prescreening_profile": (
                        asdict(request.manual_prescreening_profile)
                        if request.manual_prescreening_profile
                        else None
                    ),
                    "generated_prescreening_profile": (
                        generated_profile.model_dump() if generated_profile else None
                    ),
                    "effective_prescreening_profile": asdict(profile),
                    "generated_scenario": (
                        generated_scenario.model_dump() if generated_scenario else None
                    ),
                    "scenario_seed": request.scenario_seed,
                    "ai_prescreening_seed": request.ai_prescreening_seed,
                    "patient_persona_source": request.patient_persona_source,
                    "prescreening_step": "therapist_name",
                    "batch_id": request.batch_id,
                },
            )
            await session.execute(
                update(ConversationTrace)
                .where(ConversationTrace.trace_id == str(trace.trace_id))
                .values(
                    session_id=created.session_id,
                    sandbox_run_id=run.id,
                    sandbox_batch_id=request.batch_id,
                )
            )
            await session.execute(
                update(AgentLog)
                .where(AgentLog.trace_id == str(trace.trace_id))
                .values(
                    session_id=created.session_id,
                    sandbox_run_id=run.id,
                    sandbox_batch_id=request.batch_id,
                )
            )
            return run

    async def _resolve_prescreening_profile(
        self,
        request: SandboxSessionSpec,
        account_id: int | None = None,
    ) -> tuple[PrescreeningProfile, object | None]:
        if request.prescreening_mode == "ai_generated":
            generated = await self.auto_patient.generate_prescreening_profile(
                seed=request.ai_prescreening_seed,
                account_id=account_id,
            )
            return (
                PrescreeningProfile(
                    patient_name=generated.patient_name,
                    patient_age=generated.patient_age,
                    patient_sex=generated.patient_sex,
                    address_mode=generated.address_mode,
                    therapist_name=generated.therapist_name,
                    therapist_gender=generated.therapist_gender,
                    therapist_styles=generated.therapist_styles,
                ),
                generated,
            )
        if request.manual_prescreening_profile:
            return request.manual_prescreening_profile, None
        return (
            PrescreeningProfile(
                patient_name=request.patient_name,
                patient_age=request.patient_age,
                patient_sex=request.patient_sex,
                address_mode=request.address_mode,
            ),
            None,
        )

    async def _resolve_scenario(
        self,
        request: SandboxSessionSpec,
        profile: PrescreeningProfile,
        account_id: int | None = None,
    ):
        if request.patient_persona_source == "legacy_template":
            return None
        return await self.auto_patient.generate_scenario(
            seed=request.scenario_seed or request.ai_prescreening_seed,
            prescreening_profile=profile,
            account_id=account_id,
        )

    @staticmethod
    async def _apply_prescreening_profile(
        *,
        session,
        account_id: int,
        profile: PrescreeningProfile,
        mark_complete: bool,
    ) -> None:
        therapist_repo = TherapistPreferenceRepository(session)
        user_profile_repo = UserProfileRepository(session)
        await therapist_repo.update_preferences(
            account_id=account_id,
            therapist_name=profile.therapist_name,
            therapist_gender=profile.therapist_gender,
            therapist_styles=profile.therapist_styles,
            mark_complete=mark_complete,
        )
        await user_profile_repo.update_profile(
            account_id=account_id,
            display_name=profile.patient_name,
            age=profile.patient_age,
            sex=profile.patient_sex,
            address_mode=profile.address_mode,
            mark_complete=mark_complete,
        )

    async def send_message(
        self,
        run_id: int,
        message: str,
        model_overrides: dict | None = None,
    ) -> SandboxTurn:
        run, account = await self._load_run_account(run_id)
        run_metadata = run.run_metadata or {}
        if (
            run_metadata.get("start_phase") == "prescreening"
            and not run_metadata.get("prescreening_completed")
        ):
            return await self._send_prescreening_message(run, message, model_overrides)
        overrides = self._merge_overrides(run, model_overrides)
        started = time.perf_counter()
        with llm_overrides_scope(overrides):
            result = await self.dialogue_service.process_message(
                telegram_id=account.telegram_id,
                text=message,
                channel="sandbox",
                source="sandbox_ui",
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        async with get_db_session() as session:
            turn_repo = SandboxTurnRepository(session)
            turn = await turn_repo.create_turn(
                run_id=run.id,
                trace_id=self._extract_trace_id(result),
                patient_message=message,
                assistant_message=result.get("response", ""),
                latency_ms=latency_ms,
                metadata={
                    "session_ended": result.get("session_ended", False),
                    "strategy": result.get("strategy"),
                    "model_overrides": model_overrides,
                    "effective_config": self.llm_config_resolver.effective_config(
                        overrides=overrides,
                    ),
                },
            )
        if turn.trace_id:
            await self._link_trace_to_sandbox(
                trace_id=turn.trace_id,
                session_id=run.session_id,
                run_id=run.id,
                batch_id=run.batch_id,
            )
        return turn

    async def _send_prescreening_message(
        self,
        run: SandboxRun,
        message: str,
        model_overrides: dict | None,
    ) -> SandboxTurn:
        started = time.perf_counter()
        metadata = dict(run.run_metadata or {})
        step = metadata.get("prescreening_step") or "therapist_name"
        next_step_by_step = {
            "therapist_name": "therapist_gender",
            "therapist_gender": "patient_name",
            "patient_name": "patient_age",
            "patient_age": "patient_sex",
            "patient_sex": "address_mode",
            "address_mode": "styles",
            "styles": "completed",
        }
        next_step = next_step_by_step.get(step, "completed")
        if next_step == "completed":
            profile = self._profile_from_metadata(metadata)
            async with get_db_session() as session:
                await self._apply_prescreening_profile(
                    session=session,
                    account_id=run.account_id,
                    profile=profile,
                    mark_complete=True,
                )
                intake_repo = IntakeStateRepository(session)
                intake_state = await intake_repo.get_by_session_id(run.session_id)
                if intake_state:
                    intake_state.flow_phase = "intake"
                db_run = await SandboxRunRepository(session).get_by_id(run.id)
                if db_run:
                    next_metadata = dict(db_run.run_metadata or {})
                    next_metadata["prescreening_step"] = "completed"
                    next_metadata["prescreening_completed"] = True
                    db_run.run_metadata = next_metadata
            assistant_message = (
                "Prescreening completed in sandbox. The next patient message will enter intake."
            )
        else:
            async with get_db_session() as session:
                db_run = await SandboxRunRepository(session).get_by_id(run.id)
                if db_run:
                    next_metadata = dict(db_run.run_metadata or {})
                    next_metadata["prescreening_step"] = next_step
                    db_run.run_metadata = next_metadata
            assistant_message = self._prescreening_prompt_for_step(next_step)

        latency_ms = int((time.perf_counter() - started) * 1000)
        async with get_db_session() as session:
            turn_repo = SandboxTurnRepository(session)
            return await turn_repo.create_turn(
                run_id=run.id,
                trace_id=None,
                patient_message=message,
                assistant_message=assistant_message,
                latency_ms=latency_ms,
                metadata={
                    "flow_phase": "prescreening",
                    "prescreening_step_before": step,
                    "prescreening_step_after": next_step,
                    "model_overrides": model_overrides,
                },
            )

    async def auto_run(
        self,
        run_id: int,
        max_turns: int,
        model_overrides: dict | None = None,
    ) -> list[SandboxTurn]:
        run, account = await self._load_run_account(run_id)
        overrides = self._merge_overrides(run, model_overrides)
        template = await self._load_template(run)
        turns: list[SandboxTurn] = []
        configured_max_turns = template.max_turns if template else self.llm_config_resolver.config.sandbox.max_auto_run_turns
        for _ in range(min(max_turns, configured_max_turns)):
            conversation = await self._conversation_for_run(run.id)
            generated = await self._generate_auto_patient_message(
                run=run,
                account=account,
                template=template,
                conversation=conversation,
                overrides=overrides,
            )
            if not generated["success"] or not generated["content"]:
                break
            turn = await self.send_message(
                run.id,
                generated["content"],
                model_overrides=overrides,
            )
            turns.append(turn)
            if turn.stop_reason:
                break
        return turns

    async def run_batch(
        self,
        *,
        name: str,
        count: int,
        parallelism: int,
        max_turns_per_run: int,
        start_phase: str = "prescreening",
        prescreening_mode: str = "ai_generated",
        patient_persona_source: str = "generated",
        seed: str = "",
        model_overrides: dict | None = None,
    ):
        effective_config = self.llm_config_resolver.effective_config(
            overrides=model_overrides,
        )
        async with get_db_session() as session:
            batch = await SandboxBatchRepository(session).create_batch(
                name=name,
                requested_count=count,
                parallelism=parallelism,
                max_turns_per_run=max_turns_per_run,
                model_config=effective_config,
                metadata={
                    "requested_start_phase": start_phase,
                    "prescreening_mode": prescreening_mode,
                    "patient_persona_source": patient_persona_source,
                    "seed": seed,
                },
            )
            batch_id = batch.id

        semaphore = asyncio.Semaphore(parallelism)
        results: list[dict] = []

        async def run_one(index: int) -> dict:
            async with semaphore:
                run_seed = f"{seed or 'batch'}::{batch_id}::{index}::{uuid4()}"
                create_phase = "intake" if start_phase == "prescreening" else start_phase
                run = await self.create_session(
                    SandboxSessionSpec(
                        name=f"{name} #{index + 1}",
                        batch_id=batch_id,
                        start_phase=create_phase,
                        prescreening_mode="ai_generated",
                        ai_prescreening_seed=run_seed,
                        scenario_seed=run_seed,
                        patient_persona_source=patient_persona_source,
                        model_overrides=model_overrides,
                    )
                )
                run_metadata = dict(run.run_metadata or {})
                run_metadata["requested_start_phase"] = start_phase
                run_metadata["batch_run_index"] = index
                async with get_db_session() as session:
                    db_run = await SandboxRunRepository(session).get_by_id(run.id)
                    if db_run:
                        db_run.run_metadata = run_metadata

                turns = await self.auto_run(
                    run.id,
                    max_turns_per_run,
                    model_overrides=model_overrides,
                )
                judge_result = await self.judge_run(run.id, batch_context={"batch_id": batch_id})
                return {
                    "run_id": run.id,
                    "session_id": run.session_id,
                    "account_id": run.account_id,
                    "turns": len(turns),
                    "judge_result": judge_result,
                }

        status = "completed"
        stop_reason = None
        try:
            results = await asyncio.gather(*(run_one(i) for i in range(count)))
        except Exception as exc:
            status = "error"
            stop_reason = str(exc)
            raise
        finally:
            async with get_db_session() as session:
                repo = SandboxBatchRepository(session)
                batch = await repo.get_by_id(batch_id)
                metadata = dict(batch.batch_metadata or {}) if batch else {}
                metadata["results"] = results
                await repo.finish(
                    batch_id,
                    status=status,
                    stop_reason=stop_reason,
                    metadata=metadata,
                )

        async with get_db_session() as session:
            return await SandboxBatchRepository(session).get_by_id(batch_id)

    async def judge_run(
        self,
        run_id: int,
        *,
        batch_context: dict | None = None,
    ) -> dict:
        run, account = await self._load_run_account(run_id)
        transcript = await self._conversation_for_run(run.id)
        traces = await self._trace_payload_for_run(run)
        metadata = run.run_metadata or {}
        trace = TraceContext(channel="sandbox", source="sandbox_judge")
        trace.account_id = account.id
        trace.session_id = run.session_id
        trace.sandbox_run_id = run.id
        trace.sandbox_batch_id = run.batch_id
        started = time.perf_counter()
        status = "success"
        error_message: str | None = None
        with trace_scope(trace):
            try:
                result = await self.sandbox_judge.judge_intake_dialogue(
                    account_id=account.id,
                    session_id=run.session_id,
                    run_id=run.id,
                    transcript=transcript,
                    traces=traces,
                    profile=metadata.get("effective_prescreening_profile") or {},
                    scenario=metadata.get("generated_scenario") or {},
                    batch_context=batch_context,
                )
            except Exception as exc:
                status = "error"
                error_message = str(exc)
                raise
            finally:
                finished_at = datetime.now(timezone.utc)
                duration_ms = int((time.perf_counter() - started) * 1000)
                async with get_db_session() as session:
                    trace_repo = ConversationTraceRepository(session)
                    await trace_repo.create_from_context(
                        trace=trace,
                        status=status,
                        finished_at=finished_at,
                        duration_ms=duration_ms,
                        error_message=error_message,
                    )
        async with get_db_session() as session:
            db_run = await SandboxRunRepository(session).get_by_id(run.id)
            if db_run:
                next_metadata = dict(db_run.run_metadata or {})
                next_metadata["judge_result"] = result
                db_run.run_metadata = next_metadata
        return result

    async def stop(self, run_id: int, reason: str = "manual_stop") -> SandboxRun | None:
        async with get_db_session() as session:
            repo = SandboxRunRepository(session)
            return await repo.stop(run_id, reason)

    @staticmethod
    def _profile_from_metadata(metadata: dict) -> PrescreeningProfile:
        raw = (
            metadata.get("effective_prescreening_profile")
            or metadata.get("manual_prescreening_profile")
            or metadata.get("generated_prescreening_profile")
            or {}
        )
        return PrescreeningProfile(
            patient_name=raw.get("patient_name") or "Sandbox Пациент",
            patient_age=raw.get("patient_age"),
            patient_sex=raw.get("patient_sex") or "prefer_not_to_say",
            address_mode=raw.get("address_mode") or "formal",
            therapist_name=raw.get("therapist_name") or "Опора",
            therapist_gender=raw.get("therapist_gender") or "female",
            therapist_styles=raw.get("therapist_styles") or ["friendly"],
        )

    @staticmethod
    def _prescreening_prompt_for_step(step: str) -> str:
        prompts = {
            "therapist_gender": "Sandbox prescreening: choose counselor gender.",
            "patient_name": "Sandbox prescreening: provide patient name or pseudonym.",
            "patient_age": "Sandbox prescreening: provide patient age.",
            "patient_sex": "Sandbox prescreening: choose patient sex.",
            "address_mode": "Sandbox prescreening: choose formal or informal address.",
            "styles": "Sandbox prescreening: choose counselor communication styles.",
        }
        return prompts.get(step, "Sandbox prescreening: continue.")

    async def _load_run_account(self, run_id: int) -> tuple[SandboxRun, Account]:
        async with get_db_session() as session:
            run = await SandboxRunRepository(session).get_by_id(run_id)
            if not run:
                raise ValueError("Sandbox run not found")
            account = (
                await session.execute(select(Account).where(Account.id == run.account_id))
            ).scalar_one()
            return run, account

    async def _generate_auto_patient_message(
        self,
        *,
        run: SandboxRun,
        account: Account,
        template,
        conversation: list[dict[str, str]],
        overrides: dict | None,
    ) -> dict:
        trace = TraceContext(channel="sandbox", source="sandbox_auto_patient")
        trace.account_id = account.id
        trace.session_id = run.session_id
        trace.sandbox_run_id = run.id
        trace.sandbox_batch_id = run.batch_id
        started = time.perf_counter()
        status = "success"
        error_message: str | None = None
        with trace_scope(trace), llm_overrides_scope(overrides):
            try:
                return await self.auto_patient.next_message(
                    template=template,
                    conversation=conversation,
                    start_phase=(run.run_metadata or {}).get("start_phase", "intake"),
                    prescreening_profile=(run.run_metadata or {}).get(
                        "effective_prescreening_profile",
                        {},
                    ),
                    clinical_card=await self._clinical_card_for_account(account.id),
                    generated_scenario=(run.run_metadata or {}).get("generated_scenario", {}),
                    test_goal=(run.run_metadata or {}).get("scenario_seed", ""),
                    account_id=account.id,
                    session_id=run.session_id,
                )
            except Exception as exc:
                status = "error"
                error_message = str(exc)
                raise
            finally:
                finished_at = datetime.now(timezone.utc)
                duration_ms = int((time.perf_counter() - started) * 1000)
                async with get_db_session() as session:
                    trace_repo = ConversationTraceRepository(session)
                    await trace_repo.create_from_context(
                        trace=trace,
                        status=status,
                        finished_at=finished_at,
                        duration_ms=duration_ms,
                        error_message=error_message,
                    )

    async def _load_template(self, run: SandboxRun):
        if not run.patient_template_id:
            return None
        async with get_db_session() as session:
            repo = PatientTemplateRepository(session)
            template = await repo.get_by_id(run.patient_template_id)
            return repo.to_dataclass(template) if template else None

    async def _clinical_card_for_account(self, account_id: int) -> dict:
        async with get_db_session() as session:
            card = await ClinicalProfileRepository(session).get_patient_record(account_id)
            return card or {}

    async def _conversation_for_run(self, run_id: int) -> list[dict[str, str]]:
        async with get_db_session() as session:
            turns = await SandboxTurnRepository(session).list_for_run(run_id)
            conversation: list[dict[str, str]] = []
            for turn in turns:
                conversation.append({"role": "user", "content": turn.patient_message})
                conversation.append({"role": "assistant", "content": turn.assistant_message})
            return conversation

    async def _trace_payload_for_run(self, run: SandboxRun) -> list[dict]:
        async with get_db_session() as session:
            trace_repo = ConversationTraceRepository(session)
            log_repo = AgentLogRepository(session)
            traces = await trace_repo.get_session_traces(run.session_id)
            payload = []
            for trace in traces:
                if trace.sandbox_run_id not in (None, run.id):
                    continue
                logs = await log_repo.get_trace_logs(str(trace.trace_id))
                payload.append(
                    {
                        "trace_id": str(trace.trace_id),
                        "channel": trace.channel,
                        "source": trace.source,
                        "duration_ms": trace.duration_ms,
                        "llm_latency_ms": trace.llm_latency_ms,
                        "tokens_input": trace.total_tokens_input,
                        "tokens_output": trace.total_tokens_output,
                        "llm_calls": [
                            {
                                "agent_type": log.agent_type,
                                "task_name": log.task_name,
                                "model": log.model,
                                "latency_ms": log.latency_ms,
                                "tokens_input": log.tokens_input,
                                "tokens_output": log.tokens_output,
                                "success": log.success,
                                "error_message": log.error_message,
                                "metadata": log.extra_metadata,
                            }
                            for log in logs
                        ],
                    }
                )
            return payload

    @staticmethod
    def _new_sandbox_telegram_id() -> int:
        return SANDBOX_TELEGRAM_ID_BASE + (uuid4().int % 99_999_999)

    @staticmethod
    def _extract_trace_id(result: dict) -> str | None:
        trace = result.get("trace") if isinstance(result, dict) else None
        if isinstance(trace, dict):
            return trace.get("trace_id")
        return None

    async def _link_trace_to_sandbox(
        self,
        *,
        trace_id: str,
        session_id: int | None,
        run_id: int,
        batch_id: int | None,
    ) -> None:
        async with get_db_session() as session:
            from db.models import AgentLog, ConversationTrace
            await session.execute(
                update(ConversationTrace)
                .where(ConversationTrace.trace_id == trace_id)
                .values(
                    session_id=session_id,
                    sandbox_run_id=run_id,
                    sandbox_batch_id=batch_id,
                )
            )
            await session.execute(
                update(AgentLog)
                .where(AgentLog.trace_id == trace_id)
                .values(
                    session_id=session_id,
                    sandbox_run_id=run_id,
                    sandbox_batch_id=batch_id,
                )
            )

    @staticmethod
    def _merge_overrides(run: SandboxRun, turn_overrides: dict | None) -> dict | None:
        stored = (run.run_metadata or {}).get("model_overrides")
        if not stored and not turn_overrides:
            return None
        merged = dict(stored or {})
        for agent, tasks in (turn_overrides or {}).items():
            merged.setdefault(agent, {})
            for task, values in tasks.items():
                merged[agent].setdefault(task, {})
                merged[agent][task].update(values)
                merged[agent][task].setdefault("config_source", "turn_override")
        return merged
