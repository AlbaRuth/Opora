from pathlib import Path


def test_observability_models_have_trace_linkage_and_cost_fields() -> None:
    message = Path("db/models/message.py").read_text(encoding="utf-8")
    decision = Path("db/models/decision_log.py").read_text(encoding="utf-8")
    trace = Path("db/models/conversation_trace.py").read_text(encoding="utf-8")
    sandbox_turn = Path("db/models/sandbox_turn.py").read_text(encoding="utf-8")

    assert "trace_id" in message
    assert "trace_id" in decision
    assert "total_cost_usd" in trace
    assert "parent_trace_id" in trace
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
