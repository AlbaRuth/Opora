"""LLM judge for sandbox intake dialogue quality."""

from __future__ import annotations

import json
from typing import Any

from agents.evaluators.structured_outputs import extract_json_object
from services.llm import LlmGateway


class SandboxJudge:
    """Evaluate completed sandbox intake runs from transcript and trace metadata."""

    SYSTEM_PROMPT = """Role:
You are an independent QA judge for a psychological counseling sandbox.

Task:
Evaluate the intake-stage dialogue between an AI patient and the psychologist. Focus on:
1. Whether psychologist replies sound alive, professional, empathic, and context-aware.
2. Where architecture or agent routing created bottlenecks, poor choices, delays, or rigid logic.
3. Whether the dialogue is clinically appropriate for intake without diagnosis or direct advice.

Return JSON only with this schema:
{
  "overall_score": 0.0,
  "therapist_quality": {
    "score": 0.0,
    "findings": ["string"],
    "good_examples": ["string"],
    "bad_examples": ["string"]
  },
  "contextuality": {
    "score": 0.0,
    "findings": ["string"]
  },
  "psychologist_liveness": {
    "score": 0.0,
    "findings": ["string"]
  },
  "architecture_bottlenecks": [
    {
      "turn_number": 1,
      "component": "intake|evaluator|therapist|auto_patient|llm_gateway|unknown",
      "issue": "string",
      "evidence": "string",
      "severity": "low|medium|high"
    }
  ],
  "latency_notes": ["string"],
  "diversity_notes": ["string"],
  "recommended_fixes": ["string"]
}"""

    def __init__(self, llm_gateway: LlmGateway | None = None) -> None:
        self.llm_gateway = llm_gateway or LlmGateway()

    async def judge_intake_dialogue(
        self,
        *,
        account_id: int,
        session_id: int,
        run_id: int,
        transcript: list[dict[str, Any]],
        traces: list[dict[str, Any]],
        profile: dict[str, Any],
        scenario: dict[str, Any],
        batch_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "run_id": run_id,
            "profile": profile,
            "scenario": scenario,
            "transcript": transcript,
            "traces": traces,
            "batch_context": batch_context or {},
        }
        user_prompt = (
            "Evaluate this sandbox intake run. Use the provided transcript and trace metadata. "
            "Do not invent hidden facts beyond the payload.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        result = await self.llm_gateway.complete(
            agent_type="sandbox_judge",
            task_name="intake_dialogue_judge",
            messages=messages,
            account_id=account_id,
            session_id=session_id,
            prompt=user_prompt,
            prompt_template="SandboxJudge.judge_intake_dialogue",
            prompt_variables=payload,
            metadata={"sandbox_run_id": run_id, "batch_context": batch_context or {}},
        )
        parsed = extract_json_object(result.get("content", ""))
        if parsed:
            return parsed
        return {
            "overall_score": 0.0,
            "therapist_quality": {
                "score": 0.0,
                "findings": ["Judge returned invalid JSON."],
                "good_examples": [],
                "bad_examples": [],
            },
            "contextuality": {"score": 0.0, "findings": []},
            "psychologist_liveness": {"score": 0.0, "findings": []},
            "architecture_bottlenecks": [],
            "latency_notes": [],
            "diversity_notes": [],
            "recommended_fixes": ["Inspect raw sandbox_judge LLM log."],
        }
