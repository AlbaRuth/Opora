from dataclasses import dataclass

import pytest

from core.llm_config import LlmConfig, LlmConfigResolver, LlmGenerationConfig
from services.llm.gateway import LlmGateway


@dataclass
class CapturedLog:
    payload: dict


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "content": " Ответ ",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "latency_ms": 123,
            "reasoning": "reason",
            "provider_metadata": {"id": "gen-1"},
            "generation_params": kwargs["generation_config"].generation_params(),
            "cost_usd": 0.001,
            "success": True,
            "error": None,
        }


@pytest.mark.asyncio
async def test_llm_gateway_resolves_calls_and_logs() -> None:
    config = LlmConfig(
        defaults=LlmGenerationConfig(model="default-model", temperature=0.1, max_tokens=10),
        agents={"therapist": {"generate_response": {"model": "task-model", "max_tokens": 20}}},
    )
    client = FakeClient()
    logs: list[CapturedLog] = []

    async def log_writer(payload: dict) -> None:
        logs.append(CapturedLog(payload))

    gateway = LlmGateway(
        llm_client=client,
        llm_config=config,
        resolver=LlmConfigResolver(config),
        log_writer=log_writer,
    )

    result = await gateway.complete(
        agent_type="therapist",
        task_name="generate_response",
        messages=[{"role": "user", "content": "hello"}],
        account_id=42,
        session_id=7,
        prompt="hello",
        prompt_template="unit-test",
        prompt_variables={"name": "Ada"},
    )

    assert result["content"] == " Ответ "
    assert client.calls[0]["generation_config"].model == "task-model"
    assert logs[0].payload["agent_type"] == "therapist"
    assert logs[0].payload["task_name"] == "generate_response"
    assert logs[0].payload["model"] == "task-model"
    assert logs[0].payload["session_id"] == 7
    assert logs[0].payload["metadata"]["prompt_template"] == "unit-test"
    assert logs[0].payload["metadata"]["prompt_variables"] == {"name": "Ada"}
    assert logs[0].payload["metadata"]["prompt_truncated"] is False
    assert logs[0].payload["metadata"]["response_truncated"] is False
