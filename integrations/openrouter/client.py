"""
OpenRouter LLM client for Opora.
Centralized async client with retry logic and usage tracking.
"""

import time
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from core.config import get_settings
from core.logging import get_logger, LogContexts

logger = get_logger(LogContexts.LLM)


# Retryable HTTP status codes
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class OpenRouterClient:
    """Async OpenRouter client with retries and observability."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncOpenAI(
            base_url=self.settings.openrouter_base_url,
            api_key=self.settings.openrouter_api_key,
            timeout=self.settings.llm_timeout_seconds,
            default_headers={
                "HTTP-Referer": self.settings.openrouter_http_referer,
                "X-Title": self.settings.openrouter_app_title,
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
        model = self._normalize_model_id(model)
        max_retries = self.settings.llm_max_retries
        
        start_time = time.time()
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                completion: ChatCompletion = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                content = completion.choices[0].message.content or ""
                usage = {
                    "prompt_tokens": completion.usage.prompt_tokens if completion.usage else 0,
                    "completion_tokens": completion.usage.completion_tokens if completion.usage else 0,
                    "total_tokens": completion.usage.total_tokens if completion.usage else 0,
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
                    "success": True,
                    "error": None,
                }
                
            except Exception as e:
                last_error = str(e)
                latency_ms = int((time.time() - start_time) * 1000)
                
                # Check if error is retryable
                is_retryable = False
                if hasattr(e, "status_code") and e.status_code in _RETRYABLE_STATUS_CODES:
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
                    time.sleep(1 * (attempt + 1))  # Exponential backoff
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
                    "success": False,
                    "error": last_error,
                }
        
        # Should not reach here
        return {
            "content": "",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency_ms": int((time.time() - start_time) * 1000),
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
