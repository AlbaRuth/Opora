"""Public LLM runtime configuration loaded from JSON."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

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


class SandboxConfig(BaseModel):
    auto_patient_context_messages: int = 12
    default_auto_run_turns: int = 3
    max_auto_run_turns: int = 20


class LlmConfig(BaseModel):
    """Root JSON config."""

    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    defaults: LlmGenerationConfig
    agents: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)


_current_llm_overrides: ContextVar[dict[str, Any] | None] = ContextVar(
    "opora_llm_overrides",
    default=None,
)


def get_current_llm_overrides() -> dict[str, Any] | None:
    """Return scoped sandbox/turn overrides, if present."""

    return _current_llm_overrides.get()


@contextmanager
def llm_overrides_scope(overrides: dict[str, Any] | None) -> Iterator[None]:
    """Temporarily apply LLM overrides to all nested model calls."""

    token = _current_llm_overrides.set(overrides or None)
    try:
        yield
    finally:
        _current_llm_overrides.reset(token)


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
    """Resolve defaults + task config + scoped overrides."""

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

        scoped = get_current_llm_overrides()
        for override_source in (scoped, overrides):
            task_override = self._task_override(override_source, agent_type, task_name)
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
                    "sandbox_run_override",
                )

        return LlmGenerationConfig.model_validate(merged)

    def effective_config(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return fully resolved configs for UI/run snapshots."""

        effective: dict[str, dict[str, dict[str, Any]]] = {}
        for agent_type, tasks in self.config.agents.items():
            effective[agent_type] = {}
            for task_name in tasks:
                effective[agent_type][task_name] = self.resolve(
                    agent_type,
                    task_name,
                    overrides=overrides,
                ).model_dump(exclude_none=True)
        return {
            "provider": self.config.provider.model_dump(),
            "agents": effective,
            "logging": self.config.logging.model_dump(),
            "sandbox": self.config.sandbox.model_dump(),
        }

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
