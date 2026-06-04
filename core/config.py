"""
Centralized configuration management for Opora.
Based on Pydantic Settings pattern from SupportAssistant.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Загружать .env из корня репозитория, а не из cwd процесса (иначе при запуске
# из другой папки подставятся значения по умолчанию, например intake_min_user_turns=6).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_project_root() -> Path:
    """Return repository root used for config and relative paths."""

    return _PROJECT_ROOT


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Application
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file_enabled: bool = Field(default=True, alias="LOG_FILE_ENABLED")
    log_file_path: str = Field(default="logs/app.log", alias="LOG_FILE_PATH")
    log_file_backup_count: int = Field(default=7, alias="LOG_FILE_BACKUP_COUNT")
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://opora:opora@localhost:5432/opora",
        alias="DATABASE_URL"
    )
    
    # Telegram
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_drop_pending_on_start: bool = Field(
        default=True, 
        alias="TELEGRAM_DROP_PENDING_ON_START"
    )
    
    # OpenRouter secret. Public provider/model defaults live in config/llm_models.json.
    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")
    llm_config_path: str = Field(default="config/llm_models.json", alias="LLM_CONFIG_PATH")

    # Intake Stage Settings
    intake_enabled: bool = Field(default=True, alias="INTAKE_ENABLED")
    intake_min_user_turns: int = Field(default=6, alias="INTAKE_MIN_USER_TURNS")
    intake_required_fields: str = Field(
        default="current_problems,mental_health_history,physical_health_history",
        alias="INTAKE_REQUIRED_FIELDS",
    )
    intake_max_question_words: int = Field(default=25, alias="INTAKE_MAX_QUESTION_WORDS")
    intake_summary_max_words: int = Field(default=180, alias="INTAKE_SUMMARY_MAX_WORDS")
    intake_min_response_sentences: int = Field(
        default=3,
        alias="INTAKE_MIN_RESPONSE_SENTENCES",
    )
    intake_hold_emotion_intensity_threshold: float = Field(
        default=0.95,
        alias="INTAKE_HOLD_EMOTION_INTENSITY_THRESHOLD",
    )
    # NEW: Context window and max turns multipliers
    intake_context_window_multiplier: int = Field(
        default=2,
        alias="INTAKE_CONTEXT_WINDOW_MULTIPLIER",
    )
    intake_max_user_turns_multiplier: int = Field(
        default=2,
        alias="INTAKE_MAX_USER_TURNS_MULTIPLIER",
    )


    @property
    def is_development(self) -> bool:
        return self.app_env == "development"
    
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def intake_required_fields_list(self) -> list[str]:
        """Parse comma-separated required intake fields from env."""
        return [
            field.strip()
            for field in self.intake_required_fields.split(",")
            if field.strip()
        ]

    @property
    def intake_max_user_turns(self) -> int:
        """Hard cap on patient-side turns during intake: min × multiplier (.env)."""
        return self.intake_min_user_turns * self.intake_max_user_turns_multiplier


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
