"""Repository for profile.prescreening_states."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models import PrescreeningState


class PrescreeningStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_account_id(self, account_id: int) -> PrescreeningState | None:
        result = await self.session.execute(
            select(PrescreeningState).where(PrescreeningState.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        account_id: int,
        step: str,
        therapist_name: str = "Опора",
        therapist_gender: str = "female",
        patient_name: str = "",
        patient_age: int | None = None,
        patient_sex: str = "prefer_not_to_say",
        address_mode: str = "formal",
        selected_styles: list[str] | None = None,
        is_edit_mode: bool = False,
        processing_started_at: datetime | None = None,
    ) -> PrescreeningState:
        state = await self.get_by_account_id(account_id)
        if not state:
            state = PrescreeningState(
                account_id=account_id,
                step=step,
                therapist_name=therapist_name,
                therapist_gender=therapist_gender,
                patient_name=patient_name,
                patient_age=patient_age,
                patient_sex=patient_sex,
                address_mode=address_mode,
                selected_styles=selected_styles or [],
                is_edit_mode=is_edit_mode,
                processing_started_at=processing_started_at,
            )
            self.session.add(state)
            await self.session.flush()
            return state

        state.step = step
        state.therapist_name = therapist_name
        state.therapist_gender = therapist_gender
        state.patient_name = patient_name
        state.patient_age = patient_age
        state.patient_sex = patient_sex
        state.address_mode = address_mode
        state.selected_styles = selected_styles or []
        state.is_edit_mode = is_edit_mode
        state.processing_started_at = processing_started_at
        await self.session.flush()
        return state

    async def patch(self, account_id: int, **changes) -> PrescreeningState | None:
        state = await self.get_by_account_id(account_id)
        if not state:
            return None
        for key, value in changes.items():
            if hasattr(state, key):
                setattr(state, key, value)
        await self.session.flush()
        return state

    async def delete_by_account_id(self, account_id: int) -> bool:
        state = await self.get_by_account_id(account_id)
        if not state:
            return False
        await self.session.delete(state)
        await self.session.flush()
        return True

