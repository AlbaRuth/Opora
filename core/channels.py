"""Channel/source constants shared by transports and monitor views."""

CHANNEL_TELEGRAM = "telegram"
CHANNEL_SANDBOX = "sandbox"

# Temporary compatibility range for synthetic sandbox Telegram IDs.
# Source classification must use persisted origin, not this numeric range.
SANDBOX_TELEGRAM_ID_BASE = 900_000_000_000
