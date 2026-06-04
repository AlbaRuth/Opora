import json

from core.llm_config import (
    LlmConfigResolver,
    load_llm_config,
)


def test_load_llm_config_merges_defaults_for_all_agent_tasks(tmp_path):
    config_path = tmp_path / "llm.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": {
                    "base_url": "https://example.test/v1",
                    "http_referer": "http://localhost",
                    "app_title": "Test",
                    "timeout_seconds": 10,
                    "max_retries": 1,
                    "retry_backoff_seconds": 0.1,
                    "retryable_status_codes": [429],
                },
                "defaults": {
                    "model": "google/gemma-4-26b-a4b-it:nitro",
                    "temperature": 0.2,
                    "max_tokens": 100,
                    "top_p": 0.9,
                },
                "agents": {
                    "therapist": {
                        "generate_response": {"max_tokens": 300},
                    },
                    "evaluator": {
                        "assess_emotion": {"temperature": 0.0, "max_tokens": 50},
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    config = load_llm_config(config_path)
    resolver = LlmConfigResolver(config)

    therapist = resolver.resolve("therapist", "generate_response")
    evaluator = resolver.resolve("evaluator", "assess_emotion")

    assert therapist.model == "google/gemma-4-26b-a4b-it:nitro"
    assert therapist.temperature == 0.2
    assert therapist.max_tokens == 300
    assert therapist.top_p == 0.9
    assert evaluator.temperature == 0.0
    assert evaluator.max_tokens == 50


def test_resolver_applies_runtime_override(tmp_path):
    config_path = tmp_path / "llm.json"
    config_path.write_text(
        json.dumps(
            {
                "defaults": {
                    "model": "google/gemma-4-26b-a4b-it:nitro",
                    "temperature": 0.2,
                    "max_tokens": 100,
                },
                "agents": {
                    "therapist": {
                        "generate_response": {"temperature": 0.8, "max_tokens": 220},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    resolver = LlmConfigResolver(load_llm_config(config_path))

    resolved = resolver.resolve(
        "therapist",
        "generate_response",
        overrides={
            "therapist": {
                "generate_response": {
                    "temperature": 0.55,
                    "config_source": "runtime_override",
                }
            }
        },
    )

    assert resolved.model == "google/gemma-4-26b-a4b-it:nitro"
    assert resolved.temperature == 0.55
    assert resolved.max_tokens == 220
    assert resolved.config_source == "runtime_override"
