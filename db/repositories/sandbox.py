"""Repositories for monitor sandbox entities."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import PatientTemplateModel, SandboxRun, SandboxTurn
from monitoring.sandbox.domain import PatientTemplate

from .base import BaseRepository


class PatientTemplateRepository(BaseRepository[PatientTemplateModel]):
    """Persistence for reusable auto-patient templates."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, PatientTemplateModel)

    async def list_active(self) -> list[PatientTemplateModel]:
        result = await self.session.execute(
            select(PatientTemplateModel)
            .where(PatientTemplateModel.is_active == True)
            .order_by(PatientTemplateModel.name, PatientTemplateModel.version)
        )
        return result.scalars().all()

    async def ensure_default(self) -> PatientTemplateModel:
        result = await self.session.execute(select(PatientTemplateModel).limit(1))
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        return await self.create(
            name="Тревожный пациент",
            version=1,
            persona="Взрослый пациент, говорит коротко, сначала осторожничает.",
            presenting_problem="Тревога, усталость и напряжение перед рабочими встречами.",
            hidden_facts=["Недавно произошел конфликт с руководителем."],
            emotional_trajectory="От настороженности к умеренному доверию.",
            cooperation_level="уклончивый",
            safety_boundaries=["Не описывать самоповреждение и опасные действия."],
            max_turns=8,
            stop_conditions=["Терапевт явно завершил сессию."],
            is_active=True,
        )

    @staticmethod
    def to_dataclass(model: PatientTemplateModel) -> PatientTemplate:
        return PatientTemplate(
            name=model.name,
            persona=model.persona,
            presenting_problem=model.presenting_problem,
            hidden_facts=model.hidden_facts or [],
            emotional_trajectory=model.emotional_trajectory or "",
            cooperation_level=model.cooperation_level,
            safety_boundaries=model.safety_boundaries or [],
            max_turns=model.max_turns,
            stop_conditions=model.stop_conditions or [],
        )


class SandboxRunRepository(BaseRepository[SandboxRun]):
    """Persistence for sandbox runs."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SandboxRun)

    async def create_run(
        self,
        *,
        account_id: int,
        session_id: int,
        name: str,
        patient_template_id: int | None = None,
        model_config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SandboxRun:
        return await self.create(
            account_id=account_id,
            session_id=session_id,
            patient_template_id=patient_template_id,
            name=name,
            status="active",
            model_config=model_config,
            run_metadata=metadata,
        )

    async def stop(self, run_id: int, reason: str) -> SandboxRun | None:
        run = await self.get_by_id(run_id)
        if not run:
            return None
        return await self.update(
            run,
            status="stopped",
            stopped_at=datetime.now(UTC),
            stop_reason=reason,
        )


class SandboxTurnRepository(BaseRepository[SandboxTurn]):
    """Persistence for sandbox patient/assistant turns."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SandboxTurn)

    async def next_turn_number(self, run_id: int) -> int:
        result = await self.session.execute(
            select(func.count(SandboxTurn.id)).where(SandboxTurn.run_id == run_id)
        )
        return int(result.scalar_one() or 0) + 1

    async def create_turn(
        self,
        *,
        run_id: int,
        patient_message: str,
        assistant_message: str,
        trace_id: str | None,
        latency_ms: int | None,
        metadata: dict[str, Any] | None = None,
        stop_reason: str | None = None,
    ) -> SandboxTurn:
        return await self.create(
            run_id=run_id,
            trace_id=trace_id,
            turn_number=await self.next_turn_number(run_id),
            patient_message=patient_message,
            assistant_message=assistant_message,
            latency_ms=latency_ms,
            stop_reason=stop_reason,
            turn_metadata=metadata,
        )

    async def list_for_run(self, run_id: int) -> list[SandboxTurn]:
        result = await self.session.execute(
            select(SandboxTurn)
            .where(SandboxTurn.run_id == run_id)
            .order_by(SandboxTurn.turn_number)
        )
        return result.scalars().all()
