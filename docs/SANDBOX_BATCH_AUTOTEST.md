# Sandbox Batch Autotest

Use `POST /api/sandbox/batches` or the Monitor UI `Batch autotest` button to create
many independent sandbox intake runs.

Default QA settings:

- `count=20`
- `parallelism=5`
- `max_turns_per_run=12`
- `start_phase=prescreening`
- `prescreening_mode=ai_generated`
- `patient_persona_source=generated`

For each run, sandbox generates a fictional prescreening profile and hidden scenario,
starts the real intake path, lets `sandbox_patient.auto_patient` talk to the intake
psychologist, then calls `sandbox_judge.intake_dialogue_judge`.

The judge result is stored in `observability.sandbox_runs.metadata.judge_result` and
included in JSON/MD exports.

## Provenance

Telegram and sandbox data are separated at several levels:

- `identity.accounts.origin`: account-level source, `telegram` or `sandbox`.
- `therapy.messages.channel`: transcript-level source for each message.
- `observability.conversation_traces.channel/source`: turn source, for example
  `telegram/bot`, `sandbox/sandbox_ui`, `sandbox/sandbox_auto_patient`,
  `sandbox/sandbox_setup`, or `sandbox/sandbox_judge`.
- `observability.agent_logs.channel/source`: source for every LLM call.
- `observability.agent_logs.sandbox_run_id` and `sandbox_batch_id`: direct sandbox
  audit linkage.
- `observability.sandbox_batches`: batch metadata, status, and limits.

## API

- `POST /api/sandbox/batches`
- `GET /api/sandbox/batches/{batch_id}`
- `GET /api/sandbox/batches/{batch_id}/runs`
- `GET /api/sandbox/batches/{batch_id}/export?format=json|md`
- `GET /api/sandbox/sessions/{run_id}/export?format=json|md`
- `GET /api/chats/{session_id}/export?format=json|md`
