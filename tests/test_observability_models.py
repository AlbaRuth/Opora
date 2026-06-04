from db.models import AgentLog, ConversationTrace


def test_agent_log_has_trace_columns():
    columns = AgentLog.__table__.columns

    assert "trace_id" in columns
    assert "turn_id" in columns
    assert "channel" in columns
    assert "source" in columns
    assert "prompt_messages" in columns
    assert "provider_metadata" in columns


def test_observability_tables_are_in_observability_schema():
    assert ConversationTrace.__table__.schema == "observability"
    assert AgentLog.__table__.schema == "observability"
