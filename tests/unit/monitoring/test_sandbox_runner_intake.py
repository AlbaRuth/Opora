"""Unit tests for sandbox runner intake completion handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.models import SandboxRun, SandboxTurn
from monitoring.sandbox.runner import SandboxRunner


def _make_run() -> SandboxRun:
    run = MagicMock(spec=SandboxRun)
    run.id = 1
    run.session_id = 10
    run.batch_id = None
    run.run_metadata = {"start_phase": "intake", "prescreening_completed": True}
    return run


def _make_account():
    account = MagicMock()
    account.id = 5
    account.telegram_id = 900000001
    return account


@pytest.mark.asyncio
class TestSandboxRunnerIntake:
    async def test_send_message_sets_stop_reason_and_metadata(self):
        runner = SandboxRunner()
        run = _make_run()
        account = _make_account()
        created_turn = MagicMock(spec=SandboxTurn)
        created_turn.trace_id = "psych-trace-id"
        created_turn.stop_reason = "intake_completed"
        created_turn.turn_metadata = {
            "patient_trace_id": "patient-trace-id",
            "intake_completed": True,
            "closure_segments": {
                "therapist_closure": "Closure text",
                "extracted_summary": "Summary",
                "completion_notice": "Notice",
            },
        }

        runner._load_run_account = AsyncMock(return_value=(run, account))
        runner._merge_overrides = MagicMock(return_value={})
        runner.dialogue_service.process_message = AsyncMock(
            return_value={
                "response": "Closure text\n\nSummary\n\nNotice",
                "session_ended": False,
                "intake_completed": True,
                "closure_segments": {
                    "therapist_closure": "Closure text",
                    "extracted_summary": "Summary",
                    "completion_notice": "Notice",
                },
                "initial_info_insufficient": False,
                "strategy": {},
                "trace": {"trace_id": "psych-trace-id"},
            }
        )
        runner._link_trace_to_sandbox = AsyncMock()

        mock_turn_repo = MagicMock()
        mock_turn_repo.create_turn = AsyncMock(return_value=created_turn)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("monitoring.sandbox.runner.get_db_session", return_value=mock_session):
            with patch(
                "monitoring.sandbox.runner.SandboxTurnRepository",
                return_value=mock_turn_repo,
            ):
                turn = await runner.send_message(
                    run.id,
                    "Patient reply",
                    patient_trace_id="patient-trace-id",
                )

        assert turn is created_turn
        create_kwargs = mock_turn_repo.create_turn.await_args.kwargs
        assert create_kwargs["stop_reason"] == "intake_completed"
        assert create_kwargs["metadata"]["patient_trace_id"] == "patient-trace-id"
        assert create_kwargs["metadata"]["intake_completed"] is True
        assert create_kwargs["metadata"]["closure_segments"]["therapist_closure"] == "Closure text"
        assert runner._link_trace_to_sandbox.await_count == 2

    async def test_auto_run_stops_on_intake_completed(self):
        runner = SandboxRunner()
        run = _make_run()
        account = _make_account()

        runner._load_run_account = AsyncMock(return_value=(run, account))
        runner._merge_overrides = MagicMock(return_value={})
        runner._conversation_for_run = AsyncMock(return_value=[])
        runner.llm_config_resolver.config.sandbox.max_auto_run_turns = 10

        completed_turn = MagicMock(spec=SandboxTurn)
        completed_turn.stop_reason = "intake_completed"
        continuing_turn = MagicMock(spec=SandboxTurn)
        continuing_turn.stop_reason = None

        runner._generate_auto_patient_message = AsyncMock(
            side_effect=[
                {"success": True, "content": "msg1", "trace_id": "p1"},
                {"success": True, "content": "msg2", "trace_id": "p2"},
            ]
        )
        runner.send_message = AsyncMock(
            side_effect=[continuing_turn, completed_turn],
        )
        runner.maybe_judge_run = AsyncMock()

        turns = await runner.auto_run(run.id, max_turns=5)

        assert len(turns) == 2
        assert runner.send_message.await_count == 2
        runner.send_message.assert_any_await(
            run.id,
            "msg1",
            model_overrides={},
            patient_trace_id="p1",
        )
        runner.maybe_judge_run.assert_not_called()
