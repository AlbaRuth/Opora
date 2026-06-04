# Документация Opora v2.0

## Навигация

- **[ARCHITECTURE.md](../ARCHITECTURE.md)** — архитектура системы, слои, потоки данных
- **[DATABASE.md](DATABASE.md)** — схема БД PostgreSQL
- **[API.md](API.md)** — API репозиториев и сервисов

## Краткий обзор

### Архитектура БД — 5 PostgreSQL схем:

- `identity` — аутентификация (accounts)
- `profile` — предпочтения (user_profiles, therapist_preferences)
- `clinical` — медицинские данные (clinical_profiles)
- `therapy` — сессии и диалоги (therapy_sessions, intake_states, messages, decision_logs)
- `observability` — LLM logs и traces (agent_logs, conversation_traces)

### Быстрый старт разработки

```bash
pip install -r requirements.txt
cp .env.example .env
# Редактировать .env

alembic upgrade head
python bot_runner.py
```

## Связь с внешней документацией

- [Корневой README.md](../README.md) — общая информация и быстрый старт
- [ARCHITECTURE.md](../ARCHITECTURE.md) — подробная архитектура
- [DATABASE.md](DATABASE.md) — схема БД
- [API.md](API.md) — API репозиториев
