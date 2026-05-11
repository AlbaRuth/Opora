# Архитектура Opora

## Обзор системы

Opora - это система психологической поддержки на базе AI с персонализированным подходом. Система использует многоступенчатую архитектуру с четким разделением ответственности.

## Слои архитектуры

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Layer                          │
│         (Bot, Handlers, Prescreening Flow)                  │
├─────────────────────────────────────────────────────────────┤
│                   Service Layer                            │
│         (DialogueService - Orchestrator)                   │
├─────────────────────────────────────────────────────────────┤
│                    Agent Layer                             │
│    (TherapistAgent, IntakeAgent, Evaluators)               │
├─────────────────────────────────────────────────────────────┤
│                  Repository Layer                          │
│   (Account, Profile, Clinical, Session Repositories)       │
├─────────────────────────────────────────────────────────────┤
│                    Database Layer                          │
│   (PostgreSQL with schemas: identity, profile,            │
│    clinical, therapy, observability)                       │
└─────────────────────────────────────────────────────────────┘
```

## Компоненты

### 1. Telegram Layer (`integrations/telegram/`)
- **bot.py** - Инициализация бота и диспетчера
- **handlers.py** - Обработчики команд (/start, /anket, /summary)
- **prescreening.py** - Многошаговый wizard настройки профиля

### 2. Service Layer (`services/`)
- **dialogue_service.py** - Главный оркестратор:
  - Создание сессий
  - Маршрутизация сообщений (intake vs therapy)
  - Управление жизненным циклом диалога

### 3. Agent Layer (`agents/`)
- **TherapistAgent** - Генерация терапевтических ответов
- **IntakeAgent** - Сбор клинической информации
- **TherapistEvaluator** - Оценка эмоций и стратегий

### 4. Repository Layer (`db/repositories/`)
Новая нормализованная структура:
- **AccountRepository** - identity.accounts
- **UserProfileRepository** - profile.user_profiles
- **TherapistPreferenceRepository** - profile.therapist_preferences
- **ClinicalProfileRepository** - clinical.clinical_profiles
- **SessionRepository** - therapy.therapy_sessions
- **IntakeStateRepository** - therapy.intake_states
- **MessageRepository** - therapy.messages
- **DecisionLogRepository** - therapy.decision_logs
- **AgentLogRepository** - observability.agent_logs

## Потоки данных

### Поток Prescreening

```
/start → check_and_handle_prescreening()
    ↓
[NEW USER?] → create Account + Profiles
    ↓
Пошаговый wizard:
    1. Имя психолога
    2. Пол психолога
    3. Имя пациента
    4. Возраст
    5. Пол пациента (NEW)
    6. Стиль обращения (ты/вы) (NEW)
    7. Черты характера
    ↓
Сохранение в БД → Авто-создание сессии
```

### Поток Intake

```
Первое сообщение → IntakeAgent.process_patient_input()
    ↓
LLM анализ → Обновление clinical_profiles
    ↓
Проверка заполненности → [Полная?] → Therapy phase
    ↓
Фокусированные вопросы → Продолжение intake
```

### Поток Therapy

```
Сообщение пациента → TherapistAgent.process_patient_input()
    ↓
Оценка эмоций → Выбор стратегии → Генерация ответа
    ↓
Сохранение сообщений → Обновление сессии
```

## Новые функции (v2.0)

### Персонализация через address_mode

Система поддерживает два стиля общения:

- **formal (вы)** - формальный, уважительный стиль
- **informal (ты)** - неформальный, дружелюбный стиль

Применение:
- Промпты агентов адаптируют грамматику и обращения
- Приветствия выбираются по соответствующему стилю
- Fallback-сообщения учитывают предпочтение

### Расширенный профиль пациента

Поля профиля (`profile.user_profiles`):
- `display_name` - Отображаемое имя
- `age` - Возраст
- `sex` - Пол (male/female/prefer_not_to_say)
- `address_mode` - Стиль обращения (formal/informal)

## Безопасность данных

- Все сессии используют PostgreSQL advisory locks
- Разделение по схемам позволяет гранулированный доступ
- PII данные изолированы в identity схеме
- Audit logs в observability схеме
