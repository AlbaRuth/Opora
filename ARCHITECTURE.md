# Документация по архитектуре Opora

## Обзор

Opora — это система агента психологического консультирования со stateless-оркестрацией: runtime-состояние сессии не хранится в singleton-агенте и полностью опирается на PostgreSQL. Единственный transport — Telegram-бот.

```mermaid
flowchart TD
    TelegramBot["Telegram Bot"] --> DialogueService["DialogueService"]
    DialogueService --> Agents["Therapist, Intake, Evaluator"]
    Agents --> OpenRouter["OpenRouter"]
    DialogueService --> TherapyDB[("therapy schema")]
    Agents --> AgentLogs[("observability.agent_logs")]
    DialogueService --> Traces[("observability.conversation_traces")]
```

## Принципы проектирования

1. **Сохранение логики агента**: ключевые алгоритмы терапевтических решений не изменены относительно оригинальной реализации Opora
2. **DB-only state**: состояние сессии хранится и восстанавливается только из PostgreSQL
3. **Слоистая архитектура**: четкое разделение бизнес-логики, доступа к данным и внешних интеграций
4. **Dependency Injection**: сервисы получают зависимости через композицию
5. **Конфигурация через окружение**: все настройки вынесены в `.env`
6. **Per-session lock**: конкурирующая обработка сообщений в одной сессии сериализуется через PostgreSQL advisory lock

## Слои архитектуры

### 1. Core-слой (`core/`)

**Ответственность**: глобальная конфигурация приложения и инфраструктура

```
core/
├── config.py       # Pydantic Settings, переменные окружения
└── logging.py      # Структурированное логирование через structlog
```

**Зависимости**: отсутствуют (нижний слой)

**Ключевые классы**:
- `Settings` — централизованная конфигурация из окружения
- `configure_logging()` — настройка логирования в файл/консоль
- `LogContexts` — предопределенные имена логгеров для разных контекстов

### 2. Слой базы данных (`db/`)

**Ответственность**: хранение данных и паттерны доступа к ним

```
db/
├── models/         # ORM-модели SQLAlchemy
│   ├── base.py
│   ├── user.py
│   ├── session.py
│   ├── message.py
│   ├── decision.py
│   └── agent_log.py
├── repositories/   # Repository pattern для доступа к данным
│   ├── base.py
│   ├── user.py
│   ├── session.py
│   ├── message.py
│   ├── decision.py
│   └── agent_log.py
├── migrations/     # Миграции Alembic
├── session.py      # Управление сессиями БД
└── __init__.py
```

**Зависимости**: `core`

**Ключевые классы**:
- `User`, `TherapySession`, `Message`, `DecisionLog`, `AgentLog` — доменные модели
- `UserRepository`, `SessionRepository` и др. — абстракции доступа к данным
- `get_db_session()` — асинхронный контекст-менеджер транзакций

### 3. Слой интеграций (`integrations/`)

**Ответственность**: интеграции с внешними сервисами

```
integrations/
├── openrouter/
│   ├── client.py   # Асинхронный LLM-клиент с повторами
│   └── __init__.py
├── telegram/
│   ├── bot.py      # Фабрика и настройка бота
│   ├── handlers.py # Обработчики сообщений
│   └── __init__.py
└── __init__.py
```

**Зависимости**: `core`

**Ключевые классы**:
- `OpenRouterClient` — обертка над LLM API с retry-логикой
- `create_bot()`, `dispatcher` — настройка Telegram-бота

### 4. Слой агента (`agents/`)

**Ответственность**: логика принятия решений ИИ (СОХРАНЕНА ИЗ ОРИГИНАЛА)

```
agents/
├── core/
│   ├── session_state.py       # DTO состояния сессии (явный state-контракт)
│   ├── therapist_agent.py     # Stateless-оркестратор ответа (логика сохранена)
│   └── __init__.py
├── evaluators/
│   ├── therapist_evaluator.py # Оценка (логика evaluation.py сохранена)
│   └── __init__.py
└── prompts/
    ├── therapist_prompts.py   # Промпты генерации ответов
    ├── evaluator_prompts.py   # Промпты оценивания
    └── __init__.py
```

**Зависимости**: `core`, `integrations`, `db`

**Ключевые классы**:
- `TherapistAgent` — stateless-оркестрация терапевтической сессии
- `SessionState` — DTO состояния сессии, передаваемое между сервисом и агентом
- `TherapistEvaluator` — вся логика оценки (эмоции, стратегия, терапия)

**Сохранение логики**:
- `TherapistAgent.start_new_session()` — оригинальные строки 64-102
- `TherapistAgent.process_patient_input()` — оригинальные строки 112-204
- `TherapistAgent._generate_response()` — оригинальные строки 215-289
- `TherapistEvaluator` — сохранены все методы из `evaluation.py`

### 5. Сервисный слой (`services/`)

**Ответственность**: координация бизнес-логики

```
services/
├── dialogue_service.py   # Главная оркестрация диалога
└── __init__.py
```

**Зависимости**: `core`, `db`, `agents`, `integrations`

**Ключевые классы**:
- `DialogueService` — координирует работу Telegram, агентов и базы данных

## Потоки данных

### Поток новой сессии

```
1. Команда Telegram /start
   ↓
2. DialogueService.start_session()
   ↓
3. UserRepository.get_or_create()
   ↓
4. SessionRepository.create_session() + SessionState DTO
   ↓
5. TherapistAgent.start_new_session(state)
   ↓
6. TherapistEvaluator.cross_session_evaluate()
   ↓
7. SessionRepository.update_therapy()
   ↓
8. Возврат приветствия пользователю
```

### Поток обработки сообщений

```
1. Получено сообщение Telegram
   ↓
2. DialogueService.process_message()
   ↓
3. SessionRepository.acquire_session_lock(session_id)
   ↓
4. MessageRepository.create_message(patient)
   ↓
5. TherapistAgent.process_patient_input(state)
   └── TherapistAgent._generate_response()
       └── LlmGateway → OpenRouter
   ↓
6. MessageRepository.create_message(doctor)
   ↓
7. SessionRepository.increment_dialog_count() + update_current_stage()
   ↓
8. DecisionLogRepository.log_decision()
   ↓
9. Возврат ответа пользователю
```

### Поток наблюдаемости

```
Каждый вызов LLM:
   ↓
1. AgentLogRepository.log_llm_call() - в PostgreSQL
2. Структурированный логгер - в файл/консоль
```

## Схема базы данных

### Связи сущностей

```
┌─────────────┐       ┌──────────────────┐       ┌───────────┐
│    User     │◄──────│  TherapySession  │◄──────│  Message  │
└─────────────┘       └──────────────────┘       └───────────┘
       │                      │
       │              ┌────────┴────────┐
       │              │                 │
       │         ┌────┐           ┌───────────┐
       │         │DecisionLog     │ AgentLog  │
       │         └────────────────┴───────────┘
       │
  ┌────┴────┐
  │ AgentLog│
  └─────────┘
```

### Детали таблиц

**users**
- Основное хранилище информации о пользователе Telegram и кэшированных медицинских данных
- Связь one-to-many с `therapy_sessions` и `agent_logs`

**therapy_sessions**
- Представляет одну терапевтическую сессию диалога
- Хранит тип терапии, число реплик и статус активности
- Связь one-to-many с `messages` и `decisions`

**messages**
- Отдельные сообщения в рамках сессии
- Хранит роль (patient/doctor), текст, анализ эмоций
- Упорядочивается по `message_number` для восстановления диалога

**decision_logs**
- Снимки процесса принятия решений агентом
- Включает стратегию, эмоцию, терапию на каждом ответе
- Колонка `decision_snapshot` хранит полный JSON для аудита

**agent_logs**
- Детализированные логи вызовов LLM
- Содержит промпты, ответы, задержку и токены

## Конфигурация

Конфигурация разделена на секреты/окружение и публичные LLM-настройки.

`.env` хранит только секреты, подключения и пути:

```python
# core/config.py
class Settings(BaseSettings):
    app_env: str
    app_debug: bool
    database_url: str
    telegram_bot_token: str
    openrouter_api_key: str
    llm_config_path: str
```

`config/llm_models.json` хранит публичные и некритичные LLM-настройки:

- provider: OpenAI-compatible endpoint, headers, timeout, retry policy;
- defaults: общие `model`, `temperature`, `max_tokens`, `top_p`, penalties;
- agents: `therapist.generate_response`, `intake.intake_turn`, все evaluator-задачи;
- logging: лимиты prompt/response, сохранение prompt variables.

`core.llm_config.LlmConfigResolver` собирает effective config как `defaults + task config` (опционально — явный `overrides` на вызов).

Все LLM-вызовы пишут в `observability.agent_logs` фактические `generation_params`, `config_source`, `prompt_variables`, `prompt_truncated`, `response_truncated`, provider metadata, latency и tokens.

## Стратегия логирования

Используются три отдельных контекста логов:

1. **Service Logs** (`opora.service`)
   - инфраструктурные события
   - операции с базой данных
   - события Telegram
   - обработка ошибок

2. **Agent Logs** (`opora.agent`)
   - вызовы LLM
   - точки принятия решений
   - результаты оценок

3. **Audit Logs** (`opora.audit`)
   - события доступа к данным
   - редактирование PII
   - фокус на требованиях соответствия

Все логи включают:
- временные метки ISO
- структурированный JSON (файл) или цветной вывод в консоль
- context correlation IDs
- автоматическое редактирование PII

## Стратегия миграции

### Переход с JSON на PostgreSQL

```
Этап 1: Двойная запись (сбор данных)
- Новые данные пишутся и в JSON (бэкап), и в PostgreSQL
- Существующие JSON-данные остаются доступными

Этап 2: Миграция (разово)
- Запуск scripts/migrate_from_json.py
- Преобразование JSON-структуры в реляционную модель
- Сохранение всей исторической информации

Этап 3: Только PostgreSQL (cutover)
- Отключение записи в JSON
- Чтение исключительно из PostgreSQL
```

## Стратегия тестирования

```
tests/
├── unit/
│   ├── test_agents/        # Логика агента (сохраненное поведение)
│   ├── test_repositories/  # Доступ к данным
│   └── test_services/      # Бизнес-логика
├── integration/
│   ├── test_telegram/      # Интеграция с ботом
│   ├── test_database/      # Операции БД
│   └── test_llm/           # LLM-клиент
└── e2e/
    └── test_dialogue.py    # Полные сценарии диалога
```

## Деплой

### Docker Compose

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: opora
      POSTGRES_PASSWORD: opora
      POSTGRES_DB: opora
    volumes:
      - postgres_data:/var/lib/postgresql/data

  bot:
    build: .
    environment:
      DATABASE_URL: postgresql+asyncpg://opora:opora@postgres:5432/opora
    depends_on:
      - postgres
```

## Точки входа

- `bot_runner.py` — Telegram-бот
- `scripts/init_db.py` — инициализация базы данных
- `scripts/migrate_from_json.py` — миграция из JSON
- `scripts/migrate_intake_stage.py` — additive-миграция intake-стадии

## Intake-стадия и rollout

### Стадии процесса

- `prescreening` — сбор базового профиля через Telegram wizard
- `intake` — отдельный агент собирает карточку пациента и формирует предварительную гипотезу
- `therapy` — существующая терапевтическая логика `TherapistAgent` без смыслового изменения

Процессная стадия хранится в `therapy_sessions.flow_phase` и не конфликтует с `therapy_sessions.current_stage` (который отражает этап терапии из evaluator).

### Конфигурация intake

- `INTAKE_ENABLED` — глобальный feature-flag стадии intake
- `INTAKE_MIN_USER_TURNS` — минимальное число реплик пациента перед завершением intake
- `INTAKE_REQUIRED_FIELDS` — обязательные поля карточки
- `INTAKE_MIN_RESPONSE_SENTENCES`, `INTAKE_MAX_QUESTION_WORDS`, `INTAKE_HOLD_EMOTION_INTENSITY_THRESHOLD` — подсказки в intake-промптах; turn directives строятся в `turn_directives.py` по пробелам карточки
- LLM-параметры intake находятся в `config/llm_models.json` в `agents.intake.intake_turn`

### Релиз и откат

1. Применить `scripts/migrate_intake_stage.py` на существующей БД.
2. Включить intake в dev/staging (`INTAKE_ENABLED=true`), проверить логи в БД и structlog.
3. В production включать постепенно, отслеживая события `intake_started`, `intake_turn_processed`, `flow_phase_switched`.
4. При проблемах rollback без отката кода: `INTAKE_ENABLED=false` (роутинг вернется к прежнему терапевтическому потоку).

## Ссылки на исходный код

Вся логика агента сохранена из:

| Новый файл | Исходный файл | Строки |
|------------|---------------|--------|
| `agents/core/therapist_agent.py` | `agent/main.py` | 39-289 |
| `agents/evaluators/therapist_evaluator.py` | `agent/evaluation.py` | полностью |
| `agents/prompts/therapist_prompts.py` | `agent/main.py` | 255-271 |
| `agents/prompts/evaluator_prompts.py` | `agent/evaluation.py` | разные |

## Ключевые архитектурные решения

1. **Async-first**: все I/O-операции асинхронные (база данных, LLM, Telegram)
2. **Repository pattern**: абстрагирует доступ к данным для удобства тестирования
3. **Context managers**: сессии БД реализованы через async context manager
4. **Structured logging**: JSON-логи для production и цветная консоль для разработки
5. **Dual-source config**: переменные окружения для секретов/настроек, код — для значений по умолчанию
6. **Stateless orchestration**: mutable state удалён из `TherapistAgent`, state передаётся через DTO
7. **DB lock safety**: обработка turn внутри одной сессии защищена транзакционным advisory lock
8. **Backwards compatibility**: decision-логика и промпты сохранены без смыслового дрейфа
