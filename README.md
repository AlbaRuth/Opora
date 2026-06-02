# Opora

Opora — Telegram-бот психологического консультирования с отдельным Monitor/Sandbox сервисом для разработки, наблюдаемости и тестирования LLM-ответов без Telegram.

## Что Внутри

- `bot_runner.py` запускает только Telegram polling.
- `monitoring/api` запускает отдельный FastAPI backend для Monitor/Sandbox.
- `monitoring/web` содержит React UI: chat browser, dialog view, trace explorer, sandbox console и model overrides.
- `services/llm` содержит единый `LlmGateway`: resolve config, OpenRouter call, `observability.agent_logs`.
- `observability` содержит нейтральный trace context, не зависящий от web/monitoring слоя.
- `config/llm_models.json` хранит публичные LLM defaults и гиперпараметры; `.env` хранит секреты.

## Структура

```text
agents/                 LLM agents, evaluators, prompts
core/                   settings, channel constants, LLM config loader
db/                     SQLAlchemy models and repositories
observability/          trace context shared by bot and sandbox
services/               dialogue orchestration, LLM gateway, channel logic
integrations/telegram/  Telegram adapter and prescreening flow
integrations/openrouter OpenRouter client
monitoring/api/         FastAPI Monitor/Sandbox API
monitoring/sandbox/     Sandbox domain, runner, auto-patient
monitoring/web/         React Monitor UI
alembic/versions/       PostgreSQL migrations
docs/                   detailed architecture, DB, API and runbooks
```

## Быстрый Старт На Windows

Все Python-команды запускайте из `.venv`, если она есть:

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
MONITORING_API_TOKEN=dev-monitor-token
OBSERVABILITY_RETENTION_DAYS=90
```

Примените миграции:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

## Запуск Telegram Бота

Telegram path запускается отдельным процессом и не зависит от sandbox UI:

```powershell
.\.venv\Scripts\python.exe bot_runner.py
```

## Запуск Monitor API

Во втором терминале:

```powershell
$env:MONITORING_ENABLED="true"
$env:MONITORING_API_TOKEN="dev-monitor-token"
$env:LLM_CONFIG_PATH="config/llm_models.json"
.\.venv\Scripts\python.exe -m uvicorn monitoring.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Проверка:

```powershell
curl -H "X-API-Key: dev-monitor-token" http://127.0.0.1:8000/health
```

## Запуск React UI

В третьем терминале:

```powershell
cd monitoring\web
npm install
$env:VITE_MONITOR_API_BASE="http://127.0.0.1:8000"
$env:VITE_MONITOR_API_TOKEN="dev-monitor-token"
npm run dev
```

Откройте `http://localhost:5173`.

## Разделение Нагрузки

- Telegram bot, Monitor API и React UI запускаются разными процессами.
- Sandbox auto-run не добавляет задачи в Telegram polling loop.
- Sandbox accounts маркируются `identity.accounts.origin = 'sandbox'`; Telegram accounts — `origin = 'telegram'`.
- Monitor UI фильтрует source по persisted origin, а не по synthetic Telegram ID.
- LLM overrides из sandbox применяются через scoped config и не меняют Telegram defaults.

## Тесты И Проверки

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -c "from monitoring.api.main import app; print(app.title)"
cd monitoring\web
npm run build
```

Если PostgreSQL недоступен, DB tests могут быть skipped через fixtures.

## Документация

- `ARCHITECTURE.md` — единый источник правды по архитектуре.
- `docs/DATABASE.md` — актуальная схема БД, связи, индексы, retention.
- `docs/API.md` — API contracts.
- `docs/SANDBOX_RUNBOOK.md` — workflow sandbox и диагностика.
- `DEPLOYMENT.md` — rollout/rollback и процессная модель.
- `docs/MONITORING_SANDBOX_TZ.md` — исходное ТЗ Monitor/Sandbox.
