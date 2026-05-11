# Opora — агент психологического консультирования v2.0

Рефакторинг архитектуры с нормализованной схемой БД, персонализацией через address_mode (ты/вы) и сохранением исходной логики агента.

## Новое в v2.0

### Персонализация общения
- **Пол пациента** — выбор между мужским/женским/не хочу указывать
- **Стиль обращения** — формальный (вы) или неформальный (ты)
- Агенты адаптируют грамматику и тон в зависимости от выбора

### Нормализованная архитектура БД
- Разделение на 5 схем: identity, profile, clinical, therapy, observability
- Разделение перегруженной таблицы `users` на логические сущности
- Новая таблица `intake_states` отдельно от сессий
- Полная переработка репозиториев под новую схему

## Архитектура

```
Opora/
├── core/              # Конфигурация и логирование
├── db/                # Модели БД, репозитории, миграции
│   ├── models/        # SQLAlchemy модели по схемам
│   │   ├── account.py           # identity.accounts
│   │   ├── user_profile.py      # profile.user_profiles (NEW fields)
│   │   ├── therapist_pref.py    # profile.therapist_preferences
│   │   ├── clinical_profile.py  # clinical.clinical_profiles
│   │   ├── therapy_session.py   # therapy.therapy_sessions
│   │   ├── intake_state.py      # therapy.intake_states (NEW)
│   │   ├── message.py           # therapy.messages
│   │   ├── decision_log.py      # therapy.decision_logs
│   │   └── agent_log.py         # observability.agent_logs
│   └── repositories/  # Репозитории для каждой сущности
├── agents/            # Логика агента
│   ├── core/          # TherapistAgent, IntakeAgent, SessionState
│   ├── evaluators/    # TherapistEvaluator
│   └── prompts/       # Шаблоны промптов (NEW: address_mode)
├── integrations/      # Внешние интеграции
│   ├── telegram/      # Бот и prescreening flow (NEW steps)
│   ├── openrouter/    # LLM-клиент
│   └── langfuse/      # Наблюдаемость
├── services/          # Слой бизнес-логики (DialogueService)
├── docs/              # Документация (NEW)
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   └── API.md
└── tests/             # Набор тестов
```

## Ключевые принципы

1. **Логика агента сохранена**: вся логика принятия решений из оригинального `Opora/agent/` сохранена
2. **Новая архитектура БД**: 5 схем вместо монолитной таблицы users
3. **Персонализация**: пол пациента и стиль обращения (ты/вы) во всех промптах
4. **Слоистая архитектура**: четкое разделение между агентами, сервисами и интеграциями
5. **Конфигурация через окружение**: все настройки задаются через `.env`

## Документация

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — архитектура системы и потоки данных
- **[docs/DATABASE.md](docs/DATABASE.md)** — схема БД, таблицы, связи
- **[docs/API.md](docs/API.md)** — API репозиториев и агентов

## Быстрый старт

### 🐳 С Docker Compose (рекомендуется)

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Настроить окружение
cp .env.example .env
# Отредактируйте .env (минимум: TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY)

# 3. Запустить PostgreSQL
docker-compose up -d

# 4. Применить миграции базы данных (Alembic)
alembic upgrade head

# 5. Запустить бота
python bot_runner.py
```

### 🐘 С локальной PostgreSQL

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Настроить окружение
cp .env.example .env
# Отредактируйте .env (DATABASE_URL, TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY)

# 3. Создать базу данных в PostgreSQL (через psql/pgAdmin)
# CREATE DATABASE opora;

# 4. Применить миграции базы данных
alembic upgrade head

# 5. Запустить бота
python bot_runner.py
```

### 🛑 Остановка

```bash
# Остановить PostgreSQL
docker-compose down

# Остановить и удалить данные (осторожно!)
docker-compose down -v
```

## Миграции базы данных (Alembic)

Проект использует **Alembic** для версионирования схемы базы данных.

### Основные команды

```bash
# Показать текущую версию миграции
alembic current

# Показать историю миграций
alembic history

# Применить все миграции (для новых баз)
alembic upgrade head

# Откатить на одну версию назад (осторожно!)
alembic downgrade -1

# Создать новую миграцию после изменения моделей
alembic revision --autogenerate -m "описание изменений"
```

### Workflow для разработчиков

1. **Изменяете модели** в `db/models/`
2. **Создаете миграцию**: `alembic revision --autogenerate -m "добавлено поле X"`
3. **Проверяете SQL** в созданном файле `alembic/versions/`
4. **Применяете**: `alembic upgrade head`
5. **Тестируете** и отправляете PR с моделями + миграцией

## Тесты (pytest)

- Отдельная база PostgreSQL для тестов (пример имени: `opora_test`). URL по умолчанию задаётся в [`tests/conftest.py`](tests/conftest.py); при необходимости переопределите переменную окружения `DATABASE_URL` перед запуском.
- При старте pytest миграции Alembic до `head` выполняются синхронно в хуке `pytest_configure` (так избегается конфликт `asyncio.run` внутри уже работающего цикла событий).
- Запуск из виртуального окружения:

```bash
.\.venv\Scripts\python.exe -m pytest
```

- Тесты, которым нужна БД, будут помечены как **skipped**, если PostgreSQL недоступен или миграция не применилась.
- Нагрузочный сценарий в [`tests/integration/test_concurrent_session_handling.py`](tests/integration/test_concurrent_session_handling.py) по умолчанию отключён; чтобы включить: `set OPORA_RUN_INTEGRATION=1` (Windows) или `export OPORA_RUN_INTEGRATION=1` (Unix).

## Схема базы данных v2.0

### Схемы PostgreSQL

| Схема | Назначение | Таблицы |
|-------|-----------|---------|
| **identity** | Идентификация | `accounts` |
| **profile** | Предпочтения | `user_profiles`, `therapist_preferences` |
| **clinical** | Медицинские данные | `clinical_profiles` |
| **therapy** | Сессии и диалоги | `therapy_sessions`, `intake_states`, `messages`, `decision_logs` |
| **observability** | Логи и метрики | `agent_logs` |

### Новые поля в профиле

**profile.user_profiles**:
- `sex` — пол пациента (male/female/prefer_not_to_say)
- `address_mode` — стиль обращения (formal/informal)

## Сохранение исходной логики

Следующие файлы содержат сохраненную логику агента с расширениями:

- `agents/core/therapist_agent.py` — основная оркестрация (с NEW: address_mode)
- `agents/core/intake_agent.py` — сбор карточки (с NEW: address_mode в промптах)
- `agents/core/session_state.py` — DTO состояния (с NEW: patient_sex, address_mode)
- `agents/evaluators/therapist_evaluator.py` — логика оценки
- `agents/prompts/therapist_prompts.py` — промпты с поддержкой formal/informal
- `agents/prompts/intake_prompts.py` — промпты intake с address_mode
- `agents/prompts/evaluator_prompts.py` — промпты оценщика

## Логирование

Три потока логов:
1. **Service Logs** — инфраструктура, ошибки, события выполнения
2. **Agent Logs** — вызовы LLM, решения, рассуждения
3. **Audit Logs** — логи доступа с редактированием PII

## Переменные окружения

Поддерживаются все переменные из `.env`:

- `DATABASE_URL` — подключение к PostgreSQL
- `TELEGRAM_BOT_TOKEN` — токен бота
- `OPENROUTER_*` — настройки LLM-провайдера
- `LANGFUSE_*` — настройки наблюдаемости
- `LOG_*` — конфигурация логирования
- `INTAKE_*` — настройки intake-фазы
