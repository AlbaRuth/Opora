"""
DEPRECATED: Use Alembic migrations instead.

This script is kept for reference but superseded by Alembic revision 003.
For new deployments, use:
    alembic upgrade head

For existing databases, stamp with baseline first:
    alembic stamp 001
    alembic upgrade head

Migration script for intake stage fields.
Adds flow phase and intake counters to sessions, and hypothesis fields to users.
"""

import asyncio

from sqlalchemy import text

from core import LogContexts, configure_logging, get_logger
from db import get_engine

logger = get_logger(LogContexts.SERVICE)


async def _add_column_if_missing(conn, table_name: str, column_name: str, column_type: str) -> None:
    result = await conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = :table_name AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )

    if result.scalar_one_or_none() is None:
        logger.info("adding_column", table=table_name, column=column_name, column_type=column_type)
        await conn.execute(
            text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}")
        )
    else:
        logger.info("column_already_exists", table=table_name, column=column_name)


async def migrate() -> None:
    """Apply additive schema changes for intake stage."""
    configure_logging(level="INFO")
    logger.info("starting_intake_stage_migration")

    engine = get_engine()

    async with engine.begin() as conn:
        await _add_column_if_missing(conn, "therapy_sessions", "flow_phase", "VARCHAR(20)")
        await _add_column_if_missing(conn, "therapy_sessions", "intake_user_turns", "INTEGER")
        await _add_column_if_missing(conn, "therapy_sessions", "intake_completed_at", "TIMESTAMP WITH TIME ZONE")
        await _add_column_if_missing(conn, "users", "intake_hypothesis", "TEXT")
        await _add_column_if_missing(conn, "users", "intake_hypothesis_explanation", "TEXT")

        await conn.execute(
            text(
                """
                UPDATE therapy_sessions
                SET flow_phase = COALESCE(flow_phase, 'therapy'),
                    intake_user_turns = COALESCE(intake_user_turns, 0)
                """
            )
        )

    logger.info("intake_stage_migration_completed")


if __name__ == "__main__":
    asyncio.run(migrate())
