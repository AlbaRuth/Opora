"""
Telegram bot factory and configuration for Opora.
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import get_settings
from core.logging import get_logger, LogContexts

logger = get_logger(LogContexts.TELEGRAM)

# Create single shared dispatcher instance
dispatcher = Dispatcher()


def create_bot() -> Bot:
    """Create and configure Telegram bot."""
    settings = get_settings()
    
    logger.info("creating_telegram_bot")
    
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )


def create_dispatcher() -> Dispatcher:
    """Create aiogram dispatcher."""
    return dispatcher


async def setup_bot_on_startup(bot: Bot) -> None:
    """Setup bot on startup - clear webhooks if configured."""
    settings = get_settings()
    
    if settings.telegram_drop_pending_on_start:
        logger.info("dropping_pending_updates")
        await bot.delete_webhook(drop_pending_updates=True)
