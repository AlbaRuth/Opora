from pathlib import Path
from uuid import UUID

from observability.tracing import TraceContext, get_current_trace, trace_scope


def test_trace_scope_exposes_context_and_restores_previous_value():
    assert get_current_trace() is None

    trace = TraceContext(channel="sandbox", source="auto_patient")

    with trace_scope(trace):
        current = get_current_trace()
        assert current is trace
        assert current.channel == "sandbox"
        assert current.source == "auto_patient"
        assert UUID(str(current.trace_id))
        assert UUID(str(current.turn_id))

    assert get_current_trace() is None


def test_trace_context_accumulates_llm_usage():
    trace = TraceContext(channel="telegram", source="bot")

    trace.add_usage(prompt_tokens=12, completion_tokens=8, latency_ms=120)
    trace.add_usage(prompt_tokens=3, completion_tokens=5, latency_ms=40)

    assert trace.total_tokens_input == 15
    assert trace.total_tokens_output == 13
    assert trace.llm_latency_ms == 160


def test_production_code_does_not_import_monitoring_tracing():
    forbidden_roots = ("agents", "db", "services")

    offenders = []
    for root in forbidden_roots:
        for path in Path(root).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "monitoring.tracing" in source:
                offenders.append(str(path))

    assert offenders == []
