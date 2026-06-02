"""IntakeAgent tests with mocked LLM and DB session patch."""

import json

import pytest

from agents.core.intake_agent import IntakeAgent
from agents.core.session_state import SessionState
from db.repositories import AccountRepository, ClinicalProfileRepository


@pytest.mark.asyncio
async def test_intake_process_patient_input_updates_clinical_profile(
    db_session,
    patch_get_db_session,
    monkeypatch,
):
    patch_get_db_session("agents.core.intake_agent")
    acc_repo = AccountRepository(db_session)
    account = await acc_repo.create_from_telegram(telegram_id=99001)

    agent = IntakeAgent()
    monkeypatch.setattr(
        agent,
        "settings",
        agent.settings.model_copy(update={"intake_min_user_turns": 1}),
    )

    async def fake_llm(**kwargs):
        return {
            "success": True,
            "content": json.dumps(
                {
                    "patient_response_ru": "Понял, спасибо.",
                    "current_problems": "тревога на работе",
                    "mental_health_history": "",
                    "physical_health_history": "",
                    "intake_hypothesis": "",
                    "intake_hypothesis_explanation": "",
                    "is_intake_complete": False,
                },
                ensure_ascii=False,
            ),
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            "latency_ms": 1,
        }

    monkeypatch.setattr(agent.llm_client, "chat_completion", fake_llm)
    monkeypatch.setattr(agent, "_log_call", pytest.AsyncMock(return_value=None))

    state = SessionState(
        patient_id=str(account.id),
        session_id=f"{account.id}_1",
        session_db_id=1,
        dialog_count=0,
        session_counter=1,
        patient_display_name="Анна",
        patient_age=28,
        patient_sex="female",
        address_mode="formal",
        flow_phase="intake",
        intake_user_turns=0,
    )

    result = await agent.process_patient_input("Устал от дедлайнов", state)
    assert result["intake_completed"] is False
    assert "спасибо" in result["therapist_response"].lower()

    clinical_repo = ClinicalProfileRepository(db_session)
    profile = await clinical_repo.get_by_account_id(account.id)
    assert profile is not None
    assert profile.current_problems and "тревога" in profile.current_problems


@pytest.mark.asyncio
async def test_intake_completes_when_max_turns_reached_with_insufficient_flag(
    db_session,
    patch_get_db_session,
    monkeypatch,
):
    """Test that intake completes with insufficient flag when max turns reached."""
    patch_get_db_session("agents.core.intake_agent")
    acc_repo = AccountRepository(db_session)
    account = await acc_repo.create_from_telegram(telegram_id=99002)

    # Create clinical profile first
    clinical_repo = ClinicalProfileRepository(db_session)
    from db.models import ClinicalProfile
    profile = ClinicalProfile(
        account_id=account.id,
        current_problems="",  # Empty - will trigger insufficient flag
        mental_health_history="",
    )
    db_session.add(profile)
    await db_session.flush()

    agent = IntakeAgent()
    # Set min_user_turns=3, max_multiplier=2 -> max_turns=6
    monkeypatch.setattr(
        agent,
        "settings",
        agent.settings.model_copy(update={
            "intake_min_user_turns": 3,
            "intake_max_user_turns_multiplier": 2,
        }),
    )

    async def fake_llm(**kwargs):
        return {
            "success": True,
            "content": json.dumps(
                {
                    "patient_response_ru": "Я понял. Теперь мы перейдем к работе.",
                    "current_problems": "",  # Still empty - insufficient info
                    "mental_health_history": "",
                    "physical_health_history": "",
                    "intake_hypothesis": "недостаточно данных",
                    "intake_hypothesis_explanation": "",
                    "is_intake_complete": False,
                },
                ensure_ascii=False,
            ),
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            "latency_ms": 1,
        }

    monkeypatch.setattr(agent.llm_client, "chat_completion", fake_llm)
    monkeypatch.setattr(agent, "_log_call", pytest.AsyncMock(return_value=None))

    # Simulate 5 user turns already done, this is the 6th (max turns reached)
    state = SessionState(
        patient_id=str(account.id),
        session_id=f"{account.id}_1",
        session_db_id=1,
        dialog_count=0,
        session_counter=1,
        patient_display_name="Тест",
        patient_age=25,
        patient_sex="male",
        address_mode="formal",
        flow_phase="intake",
        intake_user_turns=5,  # 5 already done, this is #6 = max
    )

    result = await agent.process_patient_input("Тестовое сообщение", state)

    # Should be completed due to max turns
    assert result["intake_completed"] is True
    # Should have insufficient info flag
    assert result["initial_info_insufficient"] is True

    # Verify profile was updated with flag
    profile = await clinical_repo.get_by_account_id(account.id)
    assert profile.initial_info_insufficient is True
    # Explanation should have insufficient info note prepended
    assert "недостаточно информации" in profile.intake_hypothesis_explanation.lower()


@pytest.mark.asyncio
async def test_intake_context_window_computation(
    db_session,
    patch_get_db_session,
    monkeypatch,
):
    """Test that context window size is computed correctly."""
    patch_get_db_session("agents.core.intake_agent")

    agent = IntakeAgent()
    monkeypatch.setattr(
        agent,
        "settings",
        agent.settings.model_copy(update={
            "intake_min_user_turns": 6,
            "intake_context_window_multiplier": 2,
        }),
    )

    # Window size should be min_user_turns * multiplier = 12
    assert agent._get_context_window_size() == 12

    # Max turns should be min_user_turns * max_multiplier = 12
    assert agent._compute_max_user_turns() == 12


@pytest.mark.asyncio
async def test_intake_max_turns_multiplier_default(
    db_session,
    patch_get_db_session,
    monkeypatch,
):
    """Test default multiplier behavior when not explicitly set."""
    patch_get_db_session("agents.core.intake_agent")

    agent = IntakeAgent()
    # Use default settings
    monkeypatch.setattr(
        agent,
        "settings",
        agent.settings.model_copy(update={"intake_min_user_turns": 5}),
    )

    # Default multiplier is 2
    max_turns = agent._compute_max_user_turns()
    assert max_turns == 10  # 5 * 2
