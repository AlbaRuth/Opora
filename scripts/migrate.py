"""
Database migration script using Alembic.

This is the primary script for managing database schema migrations.
It uses Alembic to handle schema versioning and upgrades.

Usage:
    # Upgrade to latest version
    python scripts/migrate.py upgrade
    
    # Show current version
    python scripts/migrate.py current
    
    # Show migration history
    python scripts/migrate.py history
    
    # Downgrade one revision
    python scripts/migrate.py downgrade
    
    # Create new migration (autogenerate from model changes)
    python scripts/migrate.py revision --autogenerate -m "description"
"""

import sys
import argparse
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
    configure_logging(level="INFO")
    
    parser = argparse.ArgumentParser(
        description="Opora database migrations using Alembic"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Upgrade command
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade database")
    upgrade_parser.add_argument(
        "revision",
        nargs="?",
        default="head",
        help="Target revision (default: head)"
    )
    
    # Downgrade command
    downgrade_parser = subparsers.add_parser("downgrade", help="Downgrade database")
    downgrade_parser.add_argument(
        "revision",
        nargs="?",
        default="-1",
        help="Target revision (default: -1, one revision back)"
    )
    
    # Current command
    subparsers.add_parser("current", help="Show current revision")
    
    # History command
    subparsers.add_parser("history", help="Show migration history")
    
    # Revision command
    revision_parser = subparsers.add_parser("revision", help="Create new migration")
    revision_parser.add_argument(
        "-m", "--message",
        required=True,
        help="Migration description"
    )
    revision_parser.add_argument(
        "--autogenerate",
        action="store_true",
        help="Autogenerate from model changes"
    )
    
    # Stamp command (for existing databases)
    stamp_parser = subparsers.add_parser("stamp", help="Stamp database with revision")
    stamp_parser.add_argument(
        "revision",
        help="Revision to stamp"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Load Alembic configuration
    alembic_cfg = Config("alembic.ini")
    
    try:
        if args.command == "upgrade":
            logger.info("upgrading_database", target=args.revision)
            command.upgrade(alembic_cfg, args.revision)
            logger.info("database_upgrade_complete")
            
        elif args.command == "downgrade":
            logger.info("downgrading_database", target=args.revision)
            command.downgrade(alembic_cfg, args.revision)
            logger.info("database_downgrade_complete")
            
        elif args.command == "current":
            command.current(alembic_cfg)
            
        elif args.command == "history":
            command.history(alembic_cfg)
            
        elif args.command == "revision":
            logger.info("creating_migration", message=args.message, autogenerate=args.autogenerate)
            command.revision(
                alembic_cfg,
                message=args.message,
                autogenerate=args.autogenerate
            )
            logger.info("migration_created")
            
        elif args.command == "stamp":
            logger.info("stamping_database", revision=args.revision)
            command.stamp(alembic_cfg, args.revision)
            logger.info("database_stamped")
            
    except Exception as e:
        logger.error("migration_failed", error=str(e))
        raise


if __name__ == "__main__":
    main()
