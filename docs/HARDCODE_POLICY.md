# Dialogue Hardcode Policy

## Rule

User-dialogue meaning must not be detected with hardcoded keyword lists, regular
expressions, substring matching, or language-specific phrase triggers.

## Forbidden

- Crisis, pushback, advice request, session-end, language, active style, or response
  strategy detection with phrase lists.
- `patient_message.lower()` followed by substring checks.
- `re.search`, `re.match`, or `re.sub` for dialogue classification.
- Boolean LLM parsing by comparing raw text such as `response == "True"`.

## Allowed

- Enum values and schema field names.
- API paths, UI labels, database column names, and task names.
- Deterministic state-machine steps such as prescreening field order.
- Numeric limits and config defaults.
- Infrastructure fallback messages when LLM, database, or provider calls fail.
- JSON extraction and schema validation that do not interpret user meaning.

## Review Checklist

- New dialogue behavior has a structured LLM task or uses an existing structured
  result.
- Python code maps structured outputs to deterministic state or prompt directives.
- Prompt variables and structured outputs are logged through `LlmGateway`.
- Tests cover schema validation and policy mapping without phrase-trigger fixtures.
- Static check is reviewed for new `KEYWORDS`, `patient_message.lower()`, and regex
  usage in `agents`, `services`, and `core`.
