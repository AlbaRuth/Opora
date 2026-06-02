"""
Opora Telegram Bot Runner.
Entry point for running the Telegram bot.
Alembic migrations run in sync context before the asyncio loop (env.py uses asyncio.run).
"""

import asyncio
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config

from core import configure_logging, get_settings, get_logger, LogContexts
from db.session import verify_async_db_on_startup
from integrations.telegram import create_bot, create_dispatcher, setup_bot_on_startup, dispatcher
from services.dialogue_service import DialogueService

logger = get_logger(LogContexts.SERVICE)


def apply_alembic_migrations() -> None:
    """
    Apply Alembic migrations to head.

    Must run outside of a running event loop: alembic/env.py uses
    asyncio.run(run_async_migrations()), which conflicts with asyncio.run(main()).
    """
    project_root = Path(__file__).resolve().parent
    alembic_ini = project_root / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(project_root / "alembic"))
    command.upgrade(alembic_cfg, "head")


def apply_alembic_migrations_with_retry(
    *,
    max_wait_seconds: int = 120,
    initial_delay: float = 2.0,
) -> None:
    """
    Повторяет миграции, пока БД недоступна (контейнер postgres ещё поднимается и т.п.).
    """
    deadline = time.monotonic() + max_wait_seconds
    delay = initial_delay
    last_error: Exception | None = None
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            apply_alembic_migrations()
            if attempt > 1:
                logger.info("database_migrations_applied_after_retry", attempts=attempt)
            return
        except Exception as e:
            last_error = e
            logger.warning(
                "database_migration_attempt_failed",
                attempt=attempt,
                error=str(e),
            )
            time.sleep(delay)
            delay = min(delay * 1.5, 15.0)
    if last_error is not None:
        raise last_error
    raise RuntimeError("database_migration_retry_exhausted")


async def main():
    """Main entry point for the bot (after DB migrations)."""
    settings = get_settings()

    configure_logging(
        level=settings.log_level,
        file_enabled=settings.log_file_enabled,
        file_path=settings.log_file_path,
        backup_count=settings.log_file_backup_count,
    )

    logger.info(
        "opora_bot_starting",
        app_env=settings.app_env,
        log_level=settings.log_level,
    )

    bot = create_bot()
    dp = dispatcher

    dialogue_service = DialogueService()
    dp["dialogue_service"] = dialogue_service

    await verify_async_db_on_startup()

    await setup_bot_on_startup(bot)

    logger.info(
        "opora_system_ready",
        summary=(
            "Система полностью запущена: БД доступна, Telegram настроен, "
            "запускается приём обновлений (polling)."
        ),
    )
    logger.info("bot_started_polling")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("bot_stopped")


if __name__ == "__main__":
    try:
        settings = get_settings()
        configure_logging(
            level=settings.log_level,
            file_enabled=settings.log_file_enabled,
            file_path=settings.log_file_path,
            backup_count=settings.log_file_backup_count,
        )
        try:
            apply_alembic_migrations_with_retry()
            logger.info("database_migrations_applied")
        except Exception as e:
            logger.error(
                "database_migration_failed",
                error=str(e),
                hint=(
                    "Убедитесь, что PostgreSQL слушает порт из DATABASE_URL "
                    "(для docker-compose: из каталога Opora выполните "
                    "`docker compose up -d postgres` и при необходимости задайте в .env хост 127.0.0.1)."
                ),
            )
            sys.exit(1)

        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("bot_interrupted_by_user")
    except Exception as e:
        logger.error("bot_fatal_error", error=str(e))
        sys.exit(1)
