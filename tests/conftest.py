"""Pytest configuration and fixtures for Opora tests."""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# Add project root to sys.path for imports
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Set test environment before importing app modules
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://opora:opora@localhost:5432/opora_test"
os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
os.environ["OPENROUTER_API_KEY"] = "test_key"
os.environ["LANGFUSE_ENABLED"] = "false"
os.environ["INTAKE_ENABLED"] = "false"

# Import SessionState directly from file to avoid full app import chain
# This bypasses agents/__init__.py which triggers the circular import
sys.path.insert(0, str(_project_root / "agents" / "core"))
from session_state import SessionState
sys.path.pop(0)


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create async engine for tests - skipped if DB unavailable."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from core.config import get_settings
    
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=False,
    )
    
    # Test connection
    try:
        from db.models.base import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        await engine.dispose()
        pytest.skip(f"Database not available: {e}")
    
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional scope around a series of operations."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session() as session:
        async with session.begin():
            yield session
        await session.rollback()


@pytest.fixture
def sample_session_state() -> SessionState:
    """Create a sample SessionState for testing."""
    return SessionState(
        patient_id="123",
        session_id="123_1",
        session_db_id=1,
        dialog_count=0,
        session_counter=1,
        current_therapy="cognitive-behavioral therapy",
        current_stage="initial_assessment",
    )


@pytest.fixture
def sample_session_state_with_profile() -> SessionState:
    """Create a sample SessionState with prescreening profile for testing."""
    return SessionState(
        patient_id="123",
        session_id="123_1",
        session_db_id=1,
        dialog_count=0,
        session_counter=1,
        current_therapy="cognitive-behavioral therapy",
        current_stage="initial_assessment",
        therapist_name="Доктор Анна",
        therapist_gender="female",
        therapist_traits=["calm", "empathetic"],
        patient_display_name="Иван",
        patient_age=30,
    )


@pytest.fixture
def mock_patient_response():
    """Create a mock patient response for testing."""
    return {
        "text": "I feel anxious today",
        "attitude": "neutral",
    }


@pytest.fixture
def sample_prescreening_data():
    """Create sample prescreening data for testing."""
    return {
        "therapist_name": "Доктор Анна",
        "therapist_gender": "female",
        "patient_display_name": "Иван",
        "patient_age": 30,
        "therapist_traits": ["calm", "empathetic"],
    }
