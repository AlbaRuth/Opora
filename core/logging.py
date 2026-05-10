"""
Structured logging configuration for Opora.
Supports multiple output formats and log levels.
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict

import structlog
from structlog.processors import JSONRenderer
from structlog.stdlib import ProcessorFormatter, filter_by_level


def redact_pii(logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive information from logs."""
    sensitive_keys = {"content", "text", "message", "api_key", "token", "password"}
    
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            value = event_dict[key]
            if isinstance(value, str) and len(value) > 20:
                event_dict[key] = value[:20] + "...[REDACTED]"
            elif isinstance(value, str):
                event_dict[key] = "[REDACTED]"
    
    return event_dict


def configure_logging(
    level: str = "INFO",
    file_enabled: bool = True,
    file_path: str = "logs/app.log",
    backup_count: int = 7,
) -> None:
    """Configure structured logging for the application."""
    
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Ensure log directory exists
    if file_enabled:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Shared processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        redact_pii,
    ]
    
    # Structlog configuration
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_formatter = ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
        foreign_pre_chain=shared_processors,
    )
    console_handler.setFormatter(console_formatter)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers = []
    root_logger.addHandler(console_handler)
    
    # File handler (JSON format)
    if file_enabled:
        file_handler = TimedRotatingFileHandler(
            filename=file_path,
            when="midnight",
            interval=1,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_formatter = ProcessorFormatter(
            processor=JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Reduce noise from external libraries
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


def get_logger(name: str):
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# Predefined loggers for different contexts
class LogContexts:
    """Predefined logging contexts."""
    
    SERVICE = "opora.service"
    AGENT = "opora.agent"
    AUDIT = "opora.audit"
    TELEGRAM = "opora.telegram"
    DB = "opora.db"
    LLM = "opora.llm"
    LANGFUSE = "opora.langfuse"
