# Database Schema

Opora использует PostgreSQL и Alembic. Схема разделена по контекстам для Telegram-бота и observability.

## Schemas

- `identity`: root accounts (Telegram users).
- `profile`: user profile and therapist preferences.
- `clinical`: clinical card.
- `therapy`: sessions, messages, intake state, decisions.
- `observability`: LLM calls and end-to-end traces.

## identity.accounts

Ключевые поля:

- `id`: internal account id.
- `telegram_id`: external Telegram id (unique).
- `username`, `first_name`, `last_name`, `language_code`.

Индексы:

- `telegram_id`

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

Один user-visible turn. Связывает message, decisions и LLM calls.

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

- `trace_id`, `turn_id`, `channel`, `source`
- `account_id`, `session_id`
- `agent_type`, `task_name`, `model`, `temperature`, `max_tokens`
- `prompt`, `prompt_messages`, `response`, `reasoning`, `reasoning_summary`
- `latency_ms`, `tokens_input`, `tokens_output`, `cost_usd`
- `metadata`, `provider_metadata`, `success`, `error_message`

Индексы:

- `ix_agent_logs_trace_created(trace_id, created_at)`
- `trace_id`, `turn_id`, `channel`

## Trace Linkage

Runtime flow:

1. `DialogueService` создаёт `TraceContext`.
2. `MessageRepository` и `DecisionLogRepository` берут active `trace_id`.
3. `LlmGateway` пишет `agent_logs` и аккумулирует tokens/cost в trace context.
4. `ConversationTraceRepository` сохраняет агрегаты после завершения хода.

Prompt/response хранятся с truncation flags в `metadata`; лимиты задаются в `config/llm_models.json`.

## Alembic

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic history
```

Исторические миграции не переписываются без отдельного решения о squash.
