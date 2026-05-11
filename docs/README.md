# Документация Opora v2.0

## Навигация

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — архитектура системы, слои, потоки данных
- **[DATABASE.md](DATABASE.md)** — схема БД PostgreSQL с 5 схемами
- **[API.md](API.md)** — API репозиториев и агентов

## Краткий обзор v2.0

### Основные изменения

1. **Новая архитектура БД** — разделение на 5 PostgreSQL схем:
   - `identity` — аутентификация (accounts)
   - `profile` — предпочтения (user_profiles, therapist_preferences)
   - `clinical` — медицинские данные (clinical_profiles)
   - `therapy` — сессии и диалоги (therapy_sessions, intake_states, messages, decision_logs)
   - `observability` — логи (agent_logs)

2. **Персонализация общения** — два новых поля в профиле:
   - `sex` — пол пациента (male/female/prefer_not_to_say)
   - `address_mode` — стиль обращения (formal/вы или informal/ты)

3. **Обновленный flow прескрининга** — два новых шага:
   - Выбор пола пациента
   - Выбор стиля обращения (ты/вы)

### Миграция с v1.x

v2.0 не совместима с v1.x по схеме БД. Для чистой установки:

```bash
# Удалить старые таблицы (если есть)
drop schema public cascade;
create schema public;

# Применить новые миграции
alembic upgrade head
```

### Быстрый старт разработки

```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка окружения
cp .env.example .env
# Редактировать .env

# База данных
docker-compose up -d postgres

# Миграции
alembic upgrade head

# Запуск
python bot_runner.py
```

## Связь с внешней документацией

- [Корневой README.md](../README.md) — общая информация и быстрый старт
- [ARCHITECTURE.md](ARCHITECTURE.md) — подробная архитектура
- [DATABASE.md](DATABASE.md) — схема БД
- [API.md](API.md) — API репозиториев
