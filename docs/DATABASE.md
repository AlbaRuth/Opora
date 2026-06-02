# Схема базы данных Opora v2.0

## Обзор

База данных PostgreSQL с нормализованной структурой, разделенной на логические схемы:

```
┌─────────────────────────────────────────────────────────────┐
│                      identity                               │
│                    accounts (PK id)                         │
│              (telegram_id, username, ...)                   │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │   profile    │  │   profile    │  │  clinical    │
    │user_profiles │  │  therapist_  │  │  clinical_   │
    │(account_id  │  │ preferences  │  │ profiles     │
    │    PK/FK)    │  │(account_id  │  │(account_id   │
    │              │  │    PK/FK)    │  │    PK/FK)    │
    │  NEW fields: │  │              │  │              │
    │  - sex       │  │  - therapist │  │  - medical   │
    │  - address_  │  │    _name     │  │    history   │
    │    mode      │  │  - therapist │  │  - problems  │
    │              │  │    _gender   │  │  - intake_   │
    │              │  │  - traits    │  │    hypotesis │
    └──────────────┘  └──────────────┘  └──────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────┐
    │                        therapy                          │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
    │  │   therapy_   │  │   intake_    │  │   messages   │   │
    │  │  sessions    │  │   states     │  │              │   │
    │  │(account_id   │  │(session_id   │  │(session_id   │   │
    │  │    FK)       │  │    PK/FK)    │  │    FK)       │   │
    │  │              │  │              │  │              │   │
    │  │  - session_  │  │  NEW table:  │  │  - role      │   │
    │  │    number    │  │  - flow_     │  │  - content   │   │
    │  │  - therapy_  │  │    phase     │  │  - emotion   │   │
    │  │    type      │  │  - user_turn │  │    analysis  │   │
    │  │  - dialog_   │  │    _count     │   │              │   │
    │  │    count     │  │              │  │              │   │
    │  │              │  │              │  │              │   │
    │  └──────────────┘  └──────────────┘  └──────────────┘   │
    │  ┌──────────────┐                                      │
    │  │  decision_   │                                      │
    │  │    logs      │                                      │
    │  │(session_id   │                                      │
    │  │    FK)       │                                      │
    │  │              │                                      │
    │  │  - emotion   │                                      │
    │  │  - strategy  │                                      │
    │  │  - decision  │                                      │
    │  │    snapshot  │                                      │
    │  └──────────────┘                                      │
    └─────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────┐
    │                     observability                       │
    │                    agent_logs                           │
    │                   (account_id FK)                       │
    │                                                         │
    │  - LLM calls logging                                    │
    │  - Performance metrics                                  │
    │  - LLM call metadata (agent_logs)                       │
    └─────────────────────────────────────────────────────────┘
```

## Схемы и таблицы

### 1. identity.accounts

Корневая сущность пользователя.

| Поле | Тип | Описание |
|------|-----|----------|
| id | BigInteger PK | Внутренний ID |
| telegram_id | BigInteger Unique | ID Telegram |
| username | String(255) | @username |
| first_name | String(255) | Имя |
| last_name | String(255) | Фамилия |
| language_code | String(10) | Код языка |
| created_at | DateTime | Создание |
| updated_at | DateTime | Обновление |

### 2. profile.user_profiles

Профиль пациента с NEW полями.

| Поле | Тип | Описание |
|------|-----|----------|
| account_id | BigInteger PK/FK | Ссылка на accounts |
| display_name | String(255) | Отображаемое имя |
| age | Integer | Возраст |
| **sex** | String(20) | **NEW**: male/female/prefer_not_to_say |
| **address_mode** | String(20) | **NEW**: formal/informal |
| patient_pseudonym | String(255) | Legacy поле |
| patient_age_legacy | String(50) | Legacy поле |
| profile_completed_at | DateTime | Завершение профиля |

### 3. profile.therapist_preferences

Настройки психолога.

| Поле | Тип | Описание |
|------|-----|----------|
| account_id | BigInteger PK/FK | Ссылка на accounts |
| therapist_name | String(255) | Имя психолога |
| therapist_gender | String(20) | Пол психолога |
| therapist_traits | JSON | Черты характера |
| prescreening_completed_at | DateTime | Завершение прескрининга |

### 4. clinical.clinical_profiles

Клиническая карточка.

| Поле | Тип | Описание |
|------|-----|----------|
| account_id | BigInteger PK/FK | Ссылка на accounts |
| mental_health_history | Text | История псих. здоровья |
| physical_health_history | Text | История физ. здоровья |
| current_problems | Text | Текущие проблемы |
| intake_hypothesis | Text | Предварительная гипотеза |
| intake_hypothesis_explanation | Text | Пояснение гипотезы |

### 5. therapy.therapy_sessions

Сессии терапии.

| Поле | Тип | Описание |
|------|-----|----------|
| id | BigInteger PK | ID сессии |
| account_id | BigInteger FK | Ссылка на accounts |
| session_number | Integer | Номер сессии |
| therapy_type | String(255) | Тип терапии |
| therapy_reason | Text | Причина терапии |
| dialog_count | Integer | Счетчик диалогов |
| is_active | Boolean | Активность |
| ended_at | DateTime | Завершение |
| current_stage | Text | Текущий этап |

### 6. therapy.intake_states (NEW)

Состояние intake workflow (вынесено из therapy_sessions).

| Поле | Тип | Описание |
|------|-----|----------|
| session_id | BigInteger PK/FK | Ссылка на therapy_sessions |
| flow_phase | String(20) | Текущая фаза |
| user_turn_count | Integer | Счетчик ходов |
| completed_at | DateTime | Завершение intake |

### 7. therapy.messages

Сообщения сессии.

| Поле | Тип | Описание |
|------|-----|----------|
| id | BigInteger PK | ID сообщения |
| session_id | BigInteger FK | Ссылка на сессию |
| role | String(20) | patient/doctor |
| content | Text | Текст сообщения |
| message_number | BigInteger | Порядковый номер |
| primary_emotion | String(50) | Эмоция (cached) |
| emotional_intensity | Float | Интенсивность |

### 8. therapy.decision_logs

Логи решений агента.

| Поле | Тип | Описание |
|------|-----|----------|
| id | BigInteger PK | ID решения |
| session_id | BigInteger FK | Ссылка на сессию |
| response_number | Integer | Номер ответа |
| primary_emotion | String(50) | Эмоция |
| response_strategy | String(255) | Стратегия |
| decision_snapshot | JSON | Полный снимок |

### 9. observability.agent_logs

Логи LLM вызовов.

| Поле | Тип | Описание |
|------|-----|----------|
| id | BigInteger PK | ID лога |
| account_id | BigInteger FK | Ссылка на accounts |
| session_id | BigInteger FK | Ссылка на сессию |
| agent_type | String(50) | Тип агента |
| task_name | String(100) | Задача |
| prompt | Text | Промпт |
| response | Text | Ответ |
| latency_ms | Integer | Задержка |
| tokens_input | Integer | Токены входа |
| tokens_output | Integer | Токены выхода |

## Миграции

Все миграции управляются Alembic:

```bash
# Создание миграции
alembic revision --autogenerate -m "description"

# Применение миграций
alembic upgrade head

# Откат
alembic downgrade -1
```

Baseline миграция: `alembic/versions/001_new_schema_baseline.py`
