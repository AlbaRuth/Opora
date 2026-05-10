"""
Opora Telegram Bot Runner.
Entry point for running the Telegram bot.
"""

import asyncio
import sys

from core import configure_logging, get_settings, get_logger, LogContexts
from db import init_db
from integrations.telegram import create_bot, create_dispatcher, setup_bot_on_startup, dispatcher
from services.dialogue_service import DialogueService

logger = get_logger(LogContexts.SERVICE)


async def main():
    """Main entry point for the bot."""
    # Load settings
    settings = get_settings()
    
    # Configure logging
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
    
    # Initialize database
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        sys.exit(1)
    
    # Create bot and dispatcher
    bot = create_bot()
    dp = dispatcher
    
    # Create dialogue service with stateless agent orchestration
    dialogue_service = DialogueService()
    
    # Inject service into dispatcher context
    dp["dialogue_service"] = dialogue_service
    
    # Setup bot on startup
    await setup_bot_on_startup(bot)
    
    logger.info("bot_started_polling")
    
    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("bot_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("bot_interrupted_by_user")
    except Exception as e:
        logger.error("bot_fatal_error", error=str(e))
        sys.exit(1)
