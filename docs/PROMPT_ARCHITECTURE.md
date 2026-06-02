# Prompt Architecture

## Overview

Opora uses an LLM-first dialogue architecture. Code is responsible for routing,
validation, persistence, observability, and deterministic state transitions. Code must
not classify user dialogue with keyword lists, regular expressions, or substring rules.

## LLM Tasks

### `evaluator.dialogue_signal_analysis`

Analyzes the patient message and recent context. Returns:

```json
{
  "primary_emotion": "sadness",
  "emotional_intensity": 0.7,
  "crisis_signal": false,
  "pushback_type": "none",
  "advice_request": false,
  "question_stop": false,
  "session_end_intent": false,
  "active_style": "soft",
  "recommended_response_mode": "gentle_explore",
  "question_guidance": "encourage",
  "confidence": 0.8,
  "rationale_short": "Patient describes anxiety and can continue."
}
```

`IntakeResponsePolicy` maps this result to prompt directives. It does not inspect the
patient text.

### `intake.intake_turn`

Updates the intake card and returns the patient-facing counselor response as JSON.
It receives the structured signal result, card gaps, recent dialogue, prescreening
profile, and turn limits.

### `therapist.generate_response`

Generates the therapy-stage response. Active style comes from
`dialogue_signal_analysis`, not Python heuristics.

### `sandbox_patient.prescreening_profile_generation`

Generates fictional prescreening data from a free-form seed. It is used only when
sandbox `prescreening_mode=ai_generated`.

### `sandbox_patient.scenario_generation`

Generates a fictional clinical scenario consistent with prescreening data. For
`start_phase=therapy`, the generated card is written to the clinical profile. For
`start_phase=intake`, the scenario remains hidden patient context for auto-patient.

### `sandbox_patient.auto_patient`

Generates the next patient-side message. The prompt receives sandbox phase,
prescreening profile, clinical card, generated scenario, and recent conversation.

## Observability

All LLM tasks go through `LlmGateway`. Logs include `prompt_messages`,
`prompt_variables`, `generation_params`, `config_source`, response text, provider
metadata, latency, tokens, and trace linkage.

## Versioning

When changing a prompt contract, update:

- Pydantic structured output models in `agents/evaluators/structured_outputs.py`.
- `config/llm_models.json` task config when token or temperature needs change.
- Unit tests for parsing and policy mapping.
- `docs/PROMPT_ARCHITECTURE.md` and `docs/HARDCODE_POLICY.md`.
