from pathlib import Path


def test_observability_models_have_trace_linkage_and_cost_fields() -> None:
    message = Path("db/models/message.py").read_text(encoding="utf-8")
    decision = Path("db/models/decision_log.py").read_text(encoding="utf-8")
    trace = Path("db/models/conversation_trace.py").read_text(encoding="utf-8")
    sandbox_turn = Path("db/models/sandbox_turn.py").read_text(encoding="utf-8")
    sandbox_run = Path("db/models/sandbox_run.py").read_text(encoding="utf-8")
    agent_log = Path("db/models/agent_log.py").read_text(encoding="utf-8")

    assert "trace_id" in message
    assert "channel" in message
    assert "trace_id" in decision
    assert "total_cost_usd" in trace
    assert "parent_trace_id" in trace
    assert "sandbox_run_id" in trace
    assert "sandbox_batch_id" in trace
    assert "source" in agent_log
    assert "prompt_messages_full" in agent_log
    assert "response_full" in agent_log
    assert "sandbox_run_id" in agent_log
    assert "sandbox_batch_id" in agent_log
    assert "batch_id" in sandbox_run
    assert "observability.conversation_traces.trace_id" in sandbox_turn


def test_observability_migration_adds_indexes_constraints_and_retention_config() -> None:
    migration = Path("alembic/versions/007_observability_linkage_indexes.py").read_text(
        encoding="utf-8"
    )

    assert "ix_messages_session_number" in migration
    assert "ix_agent_logs_trace_created" in migration
    assert "uq_sandbox_turns_run_turn" in migration
    assert "fk_sandbox_turns_trace" in migration
    assert "total_cost_usd" in migration
    assert "OBSERVABILITY_RETENTION_DAYS" in Path(".env.example").read_text(encoding="utf-8")


def test_observability_provenance_migration_adds_sandbox_batches_and_sources() -> None:
    migration = Path("alembic/versions/008_observability_sources_sandbox_batches.py").read_text(
        encoding="utf-8"
    )

    assert "sandbox_batches" in migration
    assert "sandbox_batch_id" in migration
    assert "sandbox_run_id" in migration
    assert "ix_agent_logs_channel_source_created" in migration
    assert "ix_conversation_traces_channel_source_started" in migration
    assert "ix_messages_channel_session_number" in migration
    assert "prompt_messages_full" in migration
    assert "response_full" in migration
