# Prompt Architecture

## Overview

Opora uses an LLM-first dialogue architecture. Code is responsible for routing,
validation, persistence, observability, and deterministic state transitions. Code must
not classify user dialogue with keyword lists, regular expressions, or substring rules.

## LLM Tasks

### `intake.intake_turn`

Updates the intake card and returns the patient-facing counselor response as JSON.
It receives card gaps, recent dialogue, prescreening profile, and turn limits. Turn
directives are built deterministically from missing card fields (`turn_directives.py`).

### `therapist.generate_response`

Generates the therapy-stage response from session context and patient input.

## Observability

All LLM tasks go through `LlmGateway`. Logs include `prompt_messages`,
`prompt_variables`, `generation_params`, `config_source`, response text, provider
metadata, latency, tokens, and trace linkage. Every LLM call records `channel` and
`source` in `observability.agent_logs` and links to `conversation_traces`.

## Conversation Continuity

The base therapist and intake system prompts include `CONVERSATION CONTINUITY AND
PAUSES`. The model must treat goodbye, silence, and long delays as pauses in the
conversation, not as session-ending events. If the patient says goodbye, the model
closes the current turn warmly and waits for the user to return.

## Versioning

When changing a prompt contract, update:

- Pydantic structured output models in `agents/evaluators/structured_outputs.py`.
- `config/llm_models.json` task config when token or temperature needs change.
- Unit tests for parsing and policy mapping.
- `docs/PROMPT_ARCHITECTURE.md` and `docs/HARDCODE_POLICY.md`.
