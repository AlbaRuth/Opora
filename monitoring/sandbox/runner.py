"""Sandbox runner that exercises real dialogue services without Telegram."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from core.channels import CHANNEL_SANDBOX, SANDBOX_TELEGRAM_ID_BASE
from core.config import get_settings
from core.llm_config import get_llm_config_resolver, llm_overrides_scope
from db.models import Account, SandboxRun, SandboxTurn
from db.repositories import (
    AccountRepository,
    ConversationTraceRepository,
    PatientTemplateRepository,
    SandboxRunRepository,
    SandboxTurnRepository,
)
from db.session import get_db_session
from monitoring.sandbox.auto_patient import AutoPatient
from monitoring.sandbox.domain import SandboxSessionSpec
from observability.tracing import TraceContext, trace_scope
from services.dialogue_service import DialogueService
from services.session_lifecycle import create_or_replace_active_session


class SandboxRunner:
    """Create and drive synthetic chats through DialogueService."""

    def __init__(
        self,
        dialogue_service: DialogueService | None = None,
        auto_patient: AutoPatient | None = None,
    ) -> None:
        self.settings = get_settings()
        self.llm_config_resolver = get_llm_config_resolver()
        self.dialogue_service = dialogue_service or DialogueService()
        self.auto_patient = auto_patient or AutoPatient()

    async def create_session(self, request: SandboxSessionSpec) -> SandboxRun:
        telegram_id = self._new_sandbox_telegram_id()
        async with get_db_session() as session:
            account_repo = AccountRepository(session)
            template_repo = PatientTemplateRepository(session)
            run_repo = SandboxRunRepository(session)

            template = (
                await template_repo.get_by_id(request.patient_template_id)
                if request.patient_template_id
                else await template_repo.ensure_default()
            )
            account = await account_repo.create_from_telegram(
                telegram_id=telegram_id,
                username=f"sandbox_{telegram_id}",
                first_name=request.patient_name,
                language_code="ru",
                origin=CHANNEL_SANDBOX,
            )
            if account.user_profile:
                account.user_profile.display_name = request.patient_name
                account.user_profile.age = request.patient_age
                account.user_profile.sex = request.patient_sex
                account.user_profile.address_mode = request.address_mode
                account.user_profile.profile_completed_at = datetime.now(UTC)
            if account.therapist_preference:
                account.therapist_preference.prescreening_completed_at = datetime.now(UTC)
            if account.clinical_profile and template:
                account.clinical_profile.current_problems = template.presenting_problem

            created = await create_or_replace_active_session(
                account_id=account.id,
                intake_enabled=self.settings.intake_enabled,
                session=session,
            )
            return await run_repo.create_run(
                account_id=account.id,
                session_id=created.session_id,
                patient_template_id=template.id if template else None,
                name=request.name,
                model_config=self.llm_config_resolver.effective_config(
                    overrides=request.model_overrides,
                ),
                metadata={
                    "channel": "sandbox",
                    "model_overrides": request.model_overrides,
                },
            )

    async def send_message(
        self,
        run_id: int,
        message: str,
        model_overrides: dict | None = None,
    ) -> SandboxTurn:
        run, account = await self._load_run_account(run_id)
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
            return await turn_repo.create_turn(
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
        for _ in range(min(max_turns, template.max_turns)):
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

    async def stop(self, run_id: int, reason: str = "manual_stop") -> SandboxRun | None:
        async with get_db_session() as session:
            repo = SandboxRunRepository(session)
            return await repo.stop(run_id, reason)

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
        started = time.perf_counter()
        status = "success"
        error_message: str | None = None
        with trace_scope(trace), llm_overrides_scope(overrides):
            try:
                return await self.auto_patient.next_message(
                    template=template,
                    conversation=conversation,
                    account_id=account.id,
                    session_id=run.session_id,
                )
            except Exception as exc:
                status = "error"
                error_message = str(exc)
                raise
            finally:
                finished_at = datetime.now(UTC)
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
        async with get_db_session() as session:
            repo = PatientTemplateRepository(session)
            template = (
                await repo.get_by_id(run.patient_template_id)
                if run.patient_template_id
                else await repo.ensure_default()
            )
            if not template:
                template = await repo.ensure_default()
            return repo.to_dataclass(template)

    async def _conversation_for_run(self, run_id: int) -> list[dict[str, str]]:
        async with get_db_session() as session:
            turns = await SandboxTurnRepository(session).list_for_run(run_id)
            conversation: list[dict[str, str]] = []
            for turn in turns:
                conversation.append({"role": "user", "content": turn.patient_message})
                conversation.append({"role": "assistant", "content": turn.assistant_message})
            return conversation

    @staticmethod
    def _new_sandbox_telegram_id() -> int:
        return SANDBOX_TELEGRAM_ID_BASE + (uuid4().int % 99_999_999)

    @staticmethod
    def _extract_trace_id(result: dict) -> str | None:
        trace = result.get("trace") if isinstance(result, dict) else None
        if isinstance(trace, dict):
            return trace.get("trace_id")
        return None

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
