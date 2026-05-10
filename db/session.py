"""
Database session management for Opora.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings


def get_engine():
    """Get or create async database engine."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=False,
    )


def get_session_maker():
    """Get async session maker."""
    engine = get_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


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


async def init_db():
    """
    DEPRECATED: Use Alembic migrations instead.
    
    This function is kept for backward compatibility in development
    but should not be used in production. Use:
        alembic upgrade head
    
    For programmatic execution from Python code:
        from alembic import command
        from alembic.config import Config
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
    """
    import warnings
    warnings.warn(
        "init_db() is deprecated. Use 'alembic upgrade head' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # For backward compatibility, still create tables
    # but this should not be used in production
    from db.models.base import Base
    
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
