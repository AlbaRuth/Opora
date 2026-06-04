"""Public LLM runtime configuration loaded from JSON."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.config import get_project_root, get_settings


GENERATION_PARAM_KEYS = {
    "model",
    "temperature",
    "max_tokens",
    "top_p",
    "frequency_penalty",
    "presence_penalty",
    "stop",
    "seed",
    "reasoning",
}


class ProviderConfig(BaseModel):
    """OpenAI-compatible provider settings that are safe to commit."""

    base_url: str = "https://openrouter.ai/api/v1"
    http_referer: str = "http://localhost"
    app_title: str = "Opora"
    timeout_seconds: int = 120
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    retryable_status_codes: list[int] = Field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )


class LlmGenerationConfig(BaseModel):
    """Resolved generation parameters for one agent task."""

    model_config = ConfigDict(extra="allow")

    model: str
    temperature: float = 0.7
    max_tokens: int = 250
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: list[str] | str | None = None
    seed: int | None = None
    reasoning: dict[str, Any] | None = None
    config_source: str = "default_config"

    def generation_params(self) -> dict[str, Any]:
        """Return provider generation params without tracing metadata."""

        params = self.model_dump(exclude_none=True)
        params.pop("config_source", None)
        return params


class LoggingConfig(BaseModel):
    prompt_max_chars: int = 5000
    response_max_chars: int = 5000
    store_full_prompt: bool = False
    store_prompt_variables: bool = True


class LlmConfig(BaseModel):
    """Root JSON config."""

    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    defaults: LlmGenerationConfig
    agents: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_llm_config(path: str | Path) -> LlmConfig:
    """Load and validate public LLM config from JSON."""

    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = get_project_root() / config_path
    with config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return LlmConfig.model_validate(raw)


@lru_cache()
def get_llm_config() -> LlmConfig:
    """Load config using path from `.env` / Settings."""

    return load_llm_config(get_settings().llm_config_path)


@lru_cache()
def get_llm_config_resolver() -> "LlmConfigResolver":
    return LlmConfigResolver(get_llm_config())


class LlmConfigResolver:
    """Resolve defaults + task config + optional per-call overrides."""

    def __init__(self, config: LlmConfig):
        self.config = config

    def resolve(
        self,
        agent_type: str,
        task_name: str,
        overrides: dict[str, Any] | None = None,
    ) -> LlmGenerationConfig:
        merged = self.config.defaults.model_dump(exclude_none=True)
        task_config = self.config.agents.get(agent_type, {}).get(task_name, {})
        merged.update({k: v for k, v in task_config.items() if v is not None})

        task_override = self._task_override(overrides, agent_type, task_name)
        if task_override:
            merged.update(
                {
                    k: v
                    for k, v in task_override.items()
                    if k in GENERATION_PARAM_KEYS and v is not None
                }
            )
            merged["config_source"] = task_override.get(
                "config_source",
                "runtime_override",
            )

        return LlmGenerationConfig.model_validate(merged)

    @staticmethod
    def _task_override(
        overrides: dict[str, Any] | None,
        agent_type: str,
        task_name: str,
    ) -> dict[str, Any] | None:
        if not overrides:
            return None
        nested = overrides.get(agent_type)
        if isinstance(nested, dict):
            task_override = nested.get(task_name)
            if isinstance(task_override, dict):
                return task_override
        flat = overrides.get(f"{agent_type}.{task_name}")
        if isinstance(flat, dict):
            return flat
        return None
