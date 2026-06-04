# Opora

Opora — Telegram-бот психологического консультирования с LLM-агентами, PostgreSQL и observability-трейсами в БД.

## Что внутри

- `bot_runner.py` — единственная точка входа (Telegram polling).
- `services/` — оркестрация диалога (`DialogueService`), LLM gateway.
- `agents/` — intake, therapist, evaluators.
- `observability/` — trace context; запись в `conversation_traces` и `agent_logs`.
- `config/llm_models.json` — публичные LLM defaults; `.env` — секреты.

## Структура

```text
agents/                 LLM agents, evaluators, prompts
core/                   settings, LLM config loader
db/                     SQLAlchemy models and repositories
observability/          trace context for dialogue turns
services/               dialogue orchestration, LLM gateway
integrations/telegram/  Telegram adapter and prescreening flow
integrations/openrouter OpenRouter client
alembic/versions/       PostgreSQL migrations
docs/                   architecture, DB, API docs
```

## Быстрый старт (Windows)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

В `.env` задайте минимум:

```env
DATABASE_URL=postgresql+asyncpg://opora:opora@localhost:5432/opora
TELEGRAM_BOT_TOKEN=...
OPENROUTER_API_KEY=...
LLM_CONFIG_PATH=config/llm_models.json
```

Примените миграции и запустите бота:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe bot_runner.py
```

## Тесты

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Документация

- `ARCHITECTURE.md` — архитектура системы
- `docs/DATABASE.md` — схема PostgreSQL
- `docs/API.md` — API репозиториев и сервисов
- `DEPLOYMENT.md` — миграции и rollout
