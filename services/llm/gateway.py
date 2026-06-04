"""Central LLM gateway with config resolution and observability logging."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from core.llm_config import (
    LlmConfig,
    LlmGenerationConfig,
    LlmConfigResolver,
    get_llm_config,
    get_llm_config_resolver,
)
from db.repositories import AgentLogRepository
from db.session import get_db_session
from integrations.openrouter import OpenRouterClient
from observability.tracing import serialize_prompt_messages

LogWriter = Callable[[dict[str, Any]], Awaitable[None]]


class LlmGateway:
    """Resolve generation config, call the provider, and persist LLM logs."""

    def __init__(
        self,
        *,
        llm_client: Any | None = None,
        llm_config: LlmConfig | None = None,
        resolver: LlmConfigResolver | None = None,
        log_writer: LogWriter | None = None,
    ) -> None:
        self.llm_config = llm_config or get_llm_config()
        self.resolver = resolver or get_llm_config_resolver()
        self.llm_client = llm_client or OpenRouterClient()
        self._log_writer = log_writer

    async def complete(
        self,
        *,
        agent_type: str,
        task_name: str,
        messages: list[dict[str, str]],
        account_id: int | None = None,
        session_id: int | None = None,
        prompt: str | None = None,
        prompt_template: str | None = None,
        prompt_variables: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
        log: bool = True,
    ) -> dict[str, Any]:
        generation_config = self.resolver.resolve(agent_type, task_name, overrides=overrides)
        result = await self.llm_client.chat_completion(
            model=generation_config.model,
            messages=messages,
            generation_config=generation_config,
            task_name=task_name,
        )
        result["resolved_generation_config"] = generation_config.model_dump(exclude_none=True)

        if account_id is not None and log:
            await self.log_result(
                account_id=account_id,
                session_id=session_id,
                agent_type=agent_type,
                task_name=task_name,
                messages=messages,
                prompt=prompt or self._messages_to_prompt(messages),
                prompt_template=prompt_template,
                prompt_variables=prompt_variables or {},
                metadata=metadata or {},
                result=result,
                generation_config=generation_config,
            )

        return result

    async def log_result(
        self,
        *,
        account_id: int,
        session_id: int | None,
        agent_type: str,
        task_name: str,
        messages: list[dict[str, str]],
        prompt: str,
        prompt_template: str | None,
        prompt_variables: dict[str, Any],
        metadata: dict[str, Any],
        result: dict[str, Any],
        generation_config: Any | None = None,
    ) -> None:
        if generation_config is None:
            resolved = result.get("resolved_generation_config")
            generation_config = (
                LlmGenerationConfig.model_validate(resolved)
                if isinstance(resolved, dict)
                else self.resolver.resolve(agent_type, task_name)
            )
        logging_config = self.llm_config.logging
        response_text = result.get("content", "") or ""
        store_full = logging_config.store_full_prompt
        serialized_messages = serialize_prompt_messages(messages)
        prompt_truncated = bool(prompt and len(prompt) > logging_config.prompt_max_chars)
        response_truncated = bool(response_text and len(response_text) > logging_config.response_max_chars)
        payload = {
            "account_id": account_id,
            "session_id": session_id,
            "agent_type": agent_type,
            "task_name": task_name,
            "model": generation_config.model,
            "temperature": generation_config.temperature,
            "max_tokens": generation_config.max_tokens,
            "prompt": prompt[: logging_config.prompt_max_chars] if prompt else None,
            "prompt_messages": serialized_messages,
            "prompt_messages_full": serialized_messages if store_full else None,
            "response": (
                response_text[: logging_config.response_max_chars]
                if response_text
                else None
            ),
            "response_full": response_text if store_full and response_text else None,
            "prompt_truncated": prompt_truncated,
            "response_truncated": response_truncated,
            "reasoning": result.get("reasoning"),
            "latency_ms": result.get("latency_ms"),
            "tokens_input": result.get("usage", {}).get("prompt_tokens", 0),
            "tokens_output": result.get("usage", {}).get("completion_tokens", 0),
            "success": result.get("success", False),
            "error_message": result.get("error"),
            "metadata": {
                **metadata,
                "generation_params": result.get(
                    "generation_params",
                    generation_config.generation_params(),
                ),
                "config_source": generation_config.config_source,
                "prompt_template": prompt_template,
                "prompt_variables": prompt_variables,
                "prompt_truncated": prompt_truncated,
                "response_truncated": response_truncated,
            },
            "cost_usd": result.get("cost_usd"),
            "provider_metadata": result.get("provider_metadata"),
        }
        if self._log_writer:
            await self._log_writer(payload)
            return

        async with get_db_session() as session:
            await AgentLogRepository(session).log_llm_call(**payload)

    @staticmethod
    def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
        return "\n\n".join(f"{message['role']}: {message['content']}" for message in messages)
