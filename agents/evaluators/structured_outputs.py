"""Structured output helpers for evaluator LLM tasks."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError


def extract_json_object(content: Any) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response without regex heuristics."""
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return {}

    text = content.strip()
    if not text:
        return {}

    candidates = [text]
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and first < last:
        candidates.append(text[first : last + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


class ResponseStrategyResult(BaseModel):
    strategy: str = ""
    strategy_text: str = ""


class EmotionAssessmentResult(BaseModel):
    primary_emotion: str = ""
    emotional_intensity: float = Field(default=0.0, ge=0.0, le=1.0)


class TherapyProgressResult(BaseModel):
    new_therapy: str = "cognitive-behavioral therapy"
    reason: str = "maintain the original therapy"


def validate_model(model_type: type[BaseModel], content: Any) -> BaseModel | None:
    """Validate extracted JSON against a pydantic model."""
    data = extract_json_object(content)
    if not data:
        return None
    try:
        return model_type.model_validate(data)
    except ValidationError:
        return None
