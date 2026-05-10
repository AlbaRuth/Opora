"""
DEPRECATED: Use Alembic migrations instead.

This script is kept for reference but superseded by Alembic revision 002.
For new deployments, use:
    alembic upgrade head

For existing databases, stamp with baseline first:
    alembic stamp 001
    alembic upgrade head

Migration script for prescreening profile fields.
Adds new columns to users table for therapist personalization.
"""

import asyncio

from sqlalchemy import text

from core import configure_logging, get_logger, LogContexts
from db import get_engine

logger = get_logger(LogContexts.SERVICE)


async def migrate():
    """Add prescreening columns to users table."""
    configure_logging(level="INFO")
    logger.info("starting_prescreening_migration")
    
    engine = get_engine()
    
    async with engine.begin() as conn:
        # Check if columns exist and add them if not
        columns_to_add = [
            ("therapist_name", "VARCHAR(255)"),
            ("therapist_gender", "VARCHAR(20)"),
            ("patient_display_name", "VARCHAR(255)"),
            ("patient_age", "INTEGER"),
            ("therapist_traits", "JSONB"),
            ("prescreening_completed_at", "TIMESTAMP WITH TIME ZONE"),
        ]
        
        for column_name, column_type in columns_to_add:
            # Check if column exists
            result = await conn.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = :col
                """),
                {"col": column_name}
            )
            
            if result.scalar_one_or_none() is None:
                logger.info(f"adding_column", column=column_name, type=column_type)
                await conn.execute(
                    text(f'ALTER TABLE users ADD COLUMN IF NOT EXISTS {column_name} {column_type}')
                )
                logger.info(f"column_added", column=column_name)
            else:
                logger.info(f"column_already_exists", column=column_name)
        
        # Rename old patient_age to patient_age_legacy if needed
        result = await conn.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'patient_age'
            """)
        )
        
        if result.scalar_one_or_none() is not None:
            # Check if patient_age_legacy already exists
            result_legacy = await conn.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'patient_age_legacy'
                """)
            )
            
            if result_legacy.scalar_one_or_none() is None:
                logger.info("renaming_patient_age_to_legacy")
                await conn.execute(
                    text('ALTER TABLE users RENAME COLUMN patient_age TO patient_age_legacy')
                )
                logger.info("renamed_patient_age_to_legacy")
    
    logger.info("prescreening_migration_completed")


if __name__ == "__main__":
    asyncio.run(migrate())
