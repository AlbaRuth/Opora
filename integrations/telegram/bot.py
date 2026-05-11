"""
Telegram bot factory and configuration for Opora.
"""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault

from core.config import get_settings
from core.logging import get_logger, LogContexts

logger = get_logger(LogContexts.TELEGRAM)

# Create single shared dispatcher instance
dispatcher = Dispatcher()

# Bot commands configuration
BOT_COMMANDS = [
    BotCommand(command="start", description="Начать сессию / перезапустить бота"),
    BotCommand(command="anket", description="Посмотреть свою анкету"),
    BotCommand(command="summary", description="Сводка карточки пациента"),
    BotCommand(command="reset", description="Полностью очистить мои данные"),
]


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


async def setup_bot_commands(bot: Bot) -> None:
    """Setup bot commands menu (visible in Telegram UI)."""
    try:
        await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeDefault())
        logger.info("telegram_commands_set", commands_count=len(BOT_COMMANDS))
    except Exception as e:
        logger.warning("telegram_commands_set_failed", error=str(e))


async def setup_bot_on_startup(bot: Bot) -> None:
    """Setup bot on startup - clear webhooks and set commands."""
    settings = get_settings()

    if settings.telegram_drop_pending_on_start:
        logger.info("dropping_pending_updates")
        await bot.delete_webhook(drop_pending_updates=True)

    # Set up persistent commands menu
    await setup_bot_commands(bot)
