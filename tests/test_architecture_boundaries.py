from pathlib import Path


def test_sandbox_runner_does_not_depend_on_api_schemas() -> None:
    source = Path("monitoring/sandbox/runner.py").read_text(encoding="utf-8")

    assert "monitoring.api.schemas" not in source


def test_db_repositories_do_not_depend_on_monitoring_sandbox_implementation() -> None:
    offenders = []
    for path in Path("db/repositories").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "monitoring.sandbox.auto_patient" in source:
            offenders.append(str(path))

    assert offenders == []


def test_chat_source_uses_persisted_origin_not_telegram_id_range() -> None:
    chat_route = Path("monitoring/api/routes/chats.py").read_text(encoding="utf-8")
    account_model = Path("db/models/account.py").read_text(encoding="utf-8")

    assert "900_000_000_000" not in chat_route
    assert "telegram_id >=" not in chat_route
    assert "origin" in account_model
