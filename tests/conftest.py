"""Pytest configuration and fixtures for Opora tests."""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add project root to sys.path for imports
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Set test environment before importing app modules
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://opora:opora@localhost:5432/opora_test",
)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("OPENROUTER_API_KEY", "test_key")
os.environ.setdefault("LANGFUSE_ENABLED", "false")
os.environ.setdefault("INTAKE_ENABLED", "false")

# Import SessionState directly from file to avoid full app import chain
sys.path.insert(0, str(_project_root / "agents" / "core"))
from session_state import SessionState  # noqa: E402

sys.path.pop(0)


def _apply_alembic_migrations_sync() -> None:
    """Run Alembic upgrade head (sync). Keeps test DDL aligned with production."""
    from alembic import command
    from alembic.config import Config

    alembic_ini = _project_root / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(_project_root / "alembic"))
    command.upgrade(cfg, "head")


def pytest_configure(config):
    """Apply migrations once before pytest-asyncio starts an event loop (avoids nested asyncio.run in Alembic)."""
    if getattr(config.option, "collectonly", False):
        return
    try:
        _apply_alembic_migrations_sync()
    except Exception as exc:  # noqa: BLE001 — surface as skip in engine fixture
        config._opora_migration_error = exc  # noqa: SLF001


@pytest_asyncio.fixture(scope="session")
async def engine(request):
    """Create async engine; skip if DB or migrations unavailable."""
    err = getattr(request.config, "_opora_migration_error", None)
    if err:
        pytest.skip(f"Database migration unavailable: {err}")

    from core.config import get_settings

    settings = get_settings()
    eng = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=False,
    )
    try:
        async with eng.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        await eng.dispose()
        pytest.skip(f"Database not available: {e}")

    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Session bound to a connection-level transaction; rolled back after each test."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        async with session_factory() as session:
            yield session
        await trans.rollback()


@pytest.fixture
def dialogue_langfuse_stub(monkeypatch):
    """Avoid Langfuse/network during DialogueService.process_message tests."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _trace(*args, **kwargs):
        class _T:
            pass

        yield _T()

    class _LF:
        def update_trace(self, *a, **k):
            return None

    monkeypatch.setattr("services.dialogue_service.trace_scope", _trace)
    monkeypatch.setattr("services.dialogue_service.LangfuseClient", lambda: _LF())


@pytest.fixture
def patch_get_db_session(db_session, monkeypatch):
    """Patch get_db_session in a target module to reuse the test db_session (no real commit)."""

    def _install(target_module: str) -> None:
        mod = __import__(target_module, fromlist=["get_db_session"])

        @asynccontextmanager
        async def _cm():
            yield db_session

        def _factory():
            return _cm()

        monkeypatch.setattr(mod, "get_db_session", _factory)

    return _install


@pytest.fixture
def sample_session_state() -> SessionState:
    """Minimal SessionState for tests."""
    return SessionState(
        patient_id="123",
        session_id="123_1",
        session_db_id=1,
        dialog_count=0,
        session_counter=1,
        current_therapy="cognitive-behavioral therapy",
        current_stage="initial_assessment",
        flow_phase="therapy",
        intake_user_turns=0,
        patient_sex="prefer_not_to_say",
        address_mode="formal",
    )


@pytest.fixture
def sample_session_state_with_profile() -> SessionState:
    """SessionState with prescreening-style profile fields."""
    return SessionState(
        patient_id="123",
        session_id="123_1",
        session_db_id=1,
        dialog_count=0,
        session_counter=1,
        current_therapy="cognitive-behavioral therapy",
        current_stage="initial_assessment",
        flow_phase="intake",
        intake_user_turns=2,
        therapist_name="Доктор Анна",
        therapist_gender="female",
        therapist_styles=["friendly", "soft"],
        patient_display_name="Иван",
        patient_age=30,
        patient_sex="male",
        address_mode="formal",
    )


@pytest.fixture
def sample_session_state_informal() -> SessionState:
    """SessionState with informal address (ты)."""
    return SessionState(
        patient_id="456",
        session_id="456_1",
        session_db_id=2,
        dialog_count=0,
        session_counter=1,
        current_therapy="unspecified therapy",
        current_stage="",
        flow_phase="therapy",
        intake_user_turns=0,
        patient_display_name="Мария",
        patient_age=25,
        patient_sex="female",
        address_mode="informal",
    )


@pytest.fixture
def mock_patient_response():
    return {
        "text": "I feel anxious today",
        "attitude": "neutral",
    }


@pytest.fixture
def sample_prescreening_data():
    return {
        "therapist_name": "Доктор Анна",
        "therapist_gender": "female",
        "patient_display_name": "Иван",
        "patient_age": 30,
        "therapist_styles": ["calm", "empathetic"],
    }
