"""
Database initialization script using Alembic.

Creates all tables by running Alembic migrations.
For existing databases, use 'stamp' first before running this script.

Usage:
    # Initialize new database (creates all tables)
    python scripts/init_db.py
    
    # For existing databases (stamp with baseline first)
    python scripts/migrate.py stamp 001
    python scripts/migrate.py upgrade head
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from alembic import command
from alembic.config import Config
from core import configure_logging, get_logger, LogContexts

logger = get_logger(LogContexts.SERVICE)


def main():
    """Initialize database using Alembic migrations."""
    configure_logging(level="INFO")
    
    logger.info("initializing_database")
    
    try:
        # Load Alembic configuration
        alembic_cfg = Config("alembic.ini")
        
        # Run migrations to latest version
        command.upgrade(alembic_cfg, "head")
        
        logger.info("database_initialized_successfully")
        
        # Show current version
        logger.info("current_migration_version")
        command.current(alembic_cfg)
        
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        raise


if __name__ == "__main__":
    main()
