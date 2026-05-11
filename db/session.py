"""
Database session management for Opora.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("opora.db")

# Singleton engine instance
_engine: AsyncEngine | None = None
_session_maker = None


def get_engine() -> AsyncEngine:
    """Get or create async database engine (singleton)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        logger.info("db_engine_creating", database_url=settings.database_url.replace("//", "//***:***@"))
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=False,
            # Connection pool settings for better performance
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            pool_timeout=30,
        )
        logger.info("db_engine_created", pool_size=10, max_overflow=20)
    return _engine


def get_session_maker():
    """Get async session maker (singleton)."""
    global _session_maker
    if _session_maker is None:
        engine = get_engine()
        _session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_maker


async def verify_async_db_on_startup() -> None:
    """Create engine and session factory, then verify connectivity (fail fast at boot)."""
    get_session_maker()
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("db_async_connection_verified")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session as async context manager."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
