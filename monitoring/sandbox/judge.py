"""LLM judge for sandbox intake dialogue quality."""

from __future__ import annotations

import json
from typing import Any

from agents.evaluators.structured_outputs import (
    SandboxJudgeExtractionQuality,
    SandboxJudgeQualitySection,
    SandboxJudgeResult,
    extract_json_object,
    validate_model,
)
from services.llm import LlmGateway


class SandboxJudge:
    """Evaluate completed sandbox intake runs from transcript and trace metadata."""

    SYSTEM_PROMPT = """Роль:
Ты — независимый QA-судья для песочницы психологического консультирования.

Задача:
Оцени intake-диалог между AI-пациентом и психологом. Используй транскрипт, метаданные трейсов
и финальную клиническую карточку (clinical_card).

Рубрика (обязательно):
1. Качество психолога — эмпатия, живость речи, уместность вопросов, контекстность, профессиональные границы.
2. Качество extraction — насколько финальная clinical_card соответствует фактам из транскрипта:
   что упущено (missing_in_card), что добавлено без опоры на диалог (hallucinated_in_card).
3. Архитектурные bottleneck'и — по turn/component: intake, evaluator, therapist, auto_patient, llm_gateway.

Шкала score: 0.0–10.0 (десятичное). overall_verdict:
- pass — intake и extraction приемлемы для продакшена;
- needs_review — есть заметные проблемы, но не критичные;
- fail — серьёзные нарушения качества, extraction или безопасности.

Верни ТОЛЬКО JSON по схеме:
{
  "overall_score": 0.0,
  "overall_verdict": "pass|needs_review|fail",
  "therapist_quality": {
    "score": 0.0,
    "findings": ["string"],
    "good_examples": ["string"],
    "bad_examples": ["string"]
  },
  "extraction_quality": {
    "score": 0.0,
    "findings": ["string"],
    "missing_in_card": ["string"],
    "hallucinated_in_card": ["string"]
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
        clinical_card: dict[str, Any] | None = None,
        batch_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "run_id": run_id,
            "profile": profile,
            "scenario": scenario,
            "clinical_card": clinical_card or {},
            "transcript": transcript,
            "traces": traces,
            "batch_context": batch_context or {},
        }
        user_prompt = (
            "Оцени этот sandbox intake run. Используй транскрипт, трейсы и clinical_card. "
            "Не выдумывай факты вне payload.\n\n"
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
        validated = validate_model(SandboxJudgeResult, parsed)
        if validated:
            return validated.model_dump()
        if parsed:
            return parsed
        return SandboxJudgeResult(
            overall_score=0.0,
            overall_verdict="fail",
            therapist_quality=SandboxJudgeQualitySection(
                score=0.0,
                findings=["Judge вернул невалидный JSON."],
            ),
            extraction_quality=SandboxJudgeExtractionQuality(),
            recommended_fixes=["Проверьте raw sandbox_judge LLM log."],
        ).model_dump()
