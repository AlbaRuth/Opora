"""
OpenRouter LLM client for Opora.
Centralized async client with retry logic and usage tracking.
"""

import asyncio
import time
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from core.config import get_settings
from core.llm_config import LlmGenerationConfig, get_llm_config
from core.logging import get_logger, LogContexts

logger = get_logger(LogContexts.LLM)


class OpenRouterClient:
    """Async OpenRouter client with retries and observability."""
    
    def __init__(self):
        self.settings = get_settings()
        self.llm_config = get_llm_config()
        provider = self.llm_config.provider
        self.client = AsyncOpenAI(
            base_url=provider.base_url,
            api_key=self.settings.openrouter_api_key,
            timeout=provider.timeout_seconds,
            default_headers={
                "HTTP-Referer": provider.http_referer,
                "X-Title": provider.app_title,
            },
        )
    
    def _normalize_model_id(self, model: str) -> str:
        """Normalize model ID for OpenRouter."""
        # Remove openrouter/ prefix if present
        if model.startswith("openrouter/"):
            return model[11:]
        return model
    
    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 150,
        task_name: str = "unknown",
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        stop: list[str] | str | None = None,
        seed: int | None = None,
        reasoning: dict[str, Any] | None = None,
        generation_config: LlmGenerationConfig | None = None,
    ) -> dict[str, Any]:
        """
        Execute chat completion with retries.

        Returns dict with:
        - content: str
        - usage: dict with prompt_tokens, completion_tokens, total_tokens
        - latency_ms: int
        - success: bool
        - error: str | None
        """
        if generation_config is not None:
            model = generation_config.model
            temperature = generation_config.temperature
            max_tokens = generation_config.max_tokens
            top_p = generation_config.top_p
            frequency_penalty = generation_config.frequency_penalty
            presence_penalty = generation_config.presence_penalty
            stop = generation_config.stop
            seed = generation_config.seed
            reasoning = generation_config.reasoning

        model = self._normalize_model_id(model)
        provider = self.llm_config.provider
        max_retries = provider.max_retries
        retryable_status_codes = set(provider.retryable_status_codes)

        # Build kwargs dynamically to only send supported parameters
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if top_p is not None:
            kwargs["top_p"] = top_p
        if frequency_penalty is not None:
            kwargs["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            kwargs["presence_penalty"] = presence_penalty
        if stop is not None:
            kwargs["stop"] = stop
        if seed is not None:
            kwargs["seed"] = seed
        if reasoning is not None:
            kwargs["extra_body"] = {"reasoning": reasoning}

        generation_params = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "stop": stop,
            "seed": seed,
            "reasoning": reasoning,
            "config_source": generation_config.config_source if generation_config else "legacy_call",
        }

        start_time = time.time()
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                completion: ChatCompletion = await self.client.chat.completions.create(**kwargs)
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                message = completion.choices[0].message
                content = message.content or ""
                reasoning = getattr(message, "reasoning", None)
                usage = {
                    "prompt_tokens": completion.usage.prompt_tokens if completion.usage else 0,
                    "completion_tokens": completion.usage.completion_tokens if completion.usage else 0,
                    "total_tokens": completion.usage.total_tokens if completion.usage else 0,
                }
                cost_usd = getattr(completion.usage, "cost", None) if completion.usage else None
                provider_metadata = {
                    "id": completion.id,
                    "created": completion.created,
                    "model": completion.model,
                    "finish_reason": completion.choices[0].finish_reason,
                    "usage": usage,
                    "cost_usd": cost_usd,
                }
                
                logger.info(
                    "llm_request_success",
                    task=task_name,
                    model=model,
                    latency_ms=latency_ms,
                    tokens=usage,
                    attempt=attempt + 1,
                )
                
                return {
                    "content": content.strip(),
                    "usage": usage,
                    "latency_ms": latency_ms,
                    "reasoning": reasoning,
                    "provider_metadata": provider_metadata,
                    "generation_params": generation_params,
                    "cost_usd": cost_usd,
                    "success": True,
                    "error": None,
                }
                
            except Exception as e:
                last_error = str(e)
                latency_ms = int((time.time() - start_time) * 1000)
                
                # Check if error is retryable
                is_retryable = False
                if hasattr(e, "status_code") and e.status_code in retryable_status_codes:
                    is_retryable = True
                
                if attempt < max_retries and is_retryable:
                    logger.warning(
                        "llm_request_retry",
                        task=task_name,
                        model=model,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=last_error,
                    )
                    await asyncio.sleep(provider.retry_backoff_seconds * (attempt + 1))
                    continue
                
                logger.error(
                    "llm_request_failed",
                    task=task_name,
                    model=model,
                    latency_ms=latency_ms,
                    error=last_error,
                    attempts=attempt + 1,
                )
                
                return {
                    "content": "",
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "latency_ms": latency_ms,
                    "reasoning": None,
                    "provider_metadata": None,
                    "generation_params": generation_params,
                    "cost_usd": None,
                    "success": False,
                    "error": last_error,
                }
        
        # Should not reach here
        return {
            "content": "",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency_ms": int((time.time() - start_time) * 1000),
            "reasoning": None,
            "provider_metadata": None,
            "generation_params": generation_params,
            "cost_usd": None,
            "success": False,
            "error": last_error or "Unknown error",
        }
    
    async def simple_completion(
        self,
        prompt: str,
        system_message: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 150,
        task_name: str = "unknown",
    ) -> str:
        """Simple completion returning just content string."""
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]
        
        result = await self.chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            task_name=task_name,
        )
        
        if result["success"]:
            return result["content"]
        
        # Return fallback response on error
        return "Sorry, I'm temporarily unable to process your request, please try again."
