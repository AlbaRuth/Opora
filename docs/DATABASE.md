# Database Schema

Opora использует PostgreSQL и Alembic. Схема разделена по контекстам, чтобы Telegram, Sandbox и Monitor могли работать независимо, но иметь общую observability-картину.

## Schemas

- `identity`: root accounts and channel origin.
- `profile`: user profile and therapist preferences.
- `clinical`: clinical card.
- `therapy`: sessions, messages, intake state, decisions.
- `observability`: LLM calls, end-to-end traces, sandbox runs/turns/templates.

## identity.accounts

Ключевые поля:

- `id`: internal account id.
- `telegram_id`: external Telegram id or synthetic sandbox id.
- `origin`: `telegram` или `sandbox`; Monitor source filter должен использовать это поле.
- `username`, `first_name`, `last_name`, `language_code`.

Индексы:

- `telegram_id`
- `origin`

## therapy

### therapy.therapy_sessions

Сессия консультации. Важные поля: `account_id`, `session_number`, `therapy_type`, `dialog_count`, `is_active`, `current_stage`, timestamps.

Индексы/constraints:

- `ix_therapy_sessions_updated_at`
- `UNIQUE(account_id, session_number)`

### therapy.messages

Сообщения пациента и модели.

Ключевые поля:

- `session_id`, `role`, `content`, `message_number`
- `trace_id`: связь с `observability.conversation_traces.trace_id`
- `primary_emotion`, `emotional_intensity`

Индексы:

- `ix_messages_session_number(session_id, message_number)`
- `ix_messages_trace_id`

### therapy.decision_logs

Снимок агентских решений по ходу ответа.

Ключевые поля:

- `session_id`, `response_number`
- `trace_id`
- `memory_invoke_result`, `is_rejecting`, `current_therapy`, `current_stage`
- `response_strategy`, `decision_snapshot`

Индексы:

- `ix_decision_logs_session_response(session_id, response_number)`
- `ix_decision_logs_trace_id`

## observability

### observability.conversation_traces

Один user-visible turn. Связывает message, decisions, LLM calls и sandbox turn.

Ключевые поля:

- `trace_id`, `parent_trace_id`, `turn_id`
- `account_id`, `session_id`
- `channel`, `source`, `status`
- `started_at`, `finished_at`, `duration_ms`
- `llm_latency_ms`, `total_tokens_input`, `total_tokens_output`, `total_cost_usd`
- `error_message`

Индексы:

- `trace_id`, `turn_id`, `account_id`, `session_id`
- `ix_conversation_traces_session_started(session_id, started_at)`
- `ix_conversation_traces_started_at`
- `ix_conversation_traces_parent_trace_id`

### observability.agent_logs

Каждый LLM call.

Ключевые поля:

- `trace_id`, `turn_id`, `channel`
- `account_id`, `session_id`
- `agent_type`, `task_name`, `model`, `temperature`, `max_tokens`
- `prompt`, `prompt_messages`, `response`, `reasoning`, `reasoning_summary`
- `latency_ms`, `tokens_input`, `tokens_output`, `cost_usd`
- `metadata`, `provider_metadata`, `success`, `error_message`

Индексы:

- `ix_agent_logs_trace_created(trace_id, created_at)`
- `trace_id`, `turn_id`, `channel`

### observability.sandbox_runs

Sandbox session metadata.

Ключевые поля:

- `account_id`, `session_id`, `patient_template_id`
- `name`, `status`, `model_config`, `metadata`
- `stopped_at`, `stop_reason`

### observability.sandbox_turns

Patient/assistant pair inside one sandbox run.

Ключевые поля:

- `run_id`, `turn_number`
- `trace_id -> observability.conversation_traces.trace_id ON DELETE SET NULL`
- `patient_message`, `assistant_message`, `latency_ms`, `metadata`

Constraints:

- `UNIQUE(run_id, turn_number)`

### observability.patient_templates

Reusable auto-patient persona.

Constraints:

- `UNIQUE(name, version)`

## Trace Linkage

Runtime flow:

1. `DialogueService` создаёт `TraceContext`.
2. `MessageRepository` и `DecisionLogRepository` берут active `trace_id`.
3. `LlmGateway` пишет `agent_logs` и аккумулирует tokens/cost в trace context.
4. `ConversationTraceRepository` сохраняет агрегаты после завершения хода.
5. Sandbox turn сохраняет `trace_id`, чтобы UI мог открыть detail одним кликом.

## Retention

Retention управляется `OBSERVABILITY_RETENTION_DAYS` (default `90`). На текущем этапе purge/archive выполняется отдельной эксплуатационной задачей поверх:

- `observability.agent_logs`
- `observability.conversation_traces`
- `observability.sandbox_turns`

Prompt/response хранятся с truncation flags в `metadata`; лимиты задаются в `config/llm_models.json`.

## Alembic

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic history
```

Исторические миграции не переписываются без отдельного решения о squash.
