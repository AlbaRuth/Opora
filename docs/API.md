# Monitor/Sandbox API

Monitor API запускается отдельно от Telegram bot и защищается заголовком `X-API-Key`.

Base URL для локальной разработки: `http://127.0.0.1:8000`.

## Health

- `GET /health`

## Chats

- `GET /api/chats?source=telegram|sandbox`
- `GET /api/chats/{session_id}`
- `GET /api/chats/{session_id}/messages`
- `GET /api/chats/{session_id}/traces`

`source` берётся из `identity.accounts.origin`, а не из диапазона `telegram_id`.

## Traces

- `GET /api/traces/{trace_id}`

Ответ включает:

- `trace`: aggregate status, latency, tokens, cost.
- `llm_calls`: prompt messages, generation params, prompt variables, response, reasoning, provider metadata.

## Sandbox

- `POST /api/sandbox/sessions`
- `GET /api/sandbox/sessions/{run_id}`
- `POST /api/sandbox/sessions/{run_id}/messages`
- `POST /api/sandbox/sessions/{run_id}/auto-run`
- `POST /api/sandbox/sessions/{run_id}/stop`
- `GET /api/sandbox/sessions/{run_id}/turns`
- `GET /api/sandbox/templates/patients`
- `GET /api/sandbox/model-config`

Sandbox requests may include `model_overrides`. Overrides are scoped to run/turn and do not mutate `config/llm_models.json`.

# API Documentation

## Repository API

### AccountRepository

```python
from db.repositories import AccountRepository

# Получение по Telegram ID
account = await account_repo.get_by_telegram_id(telegram_id)

# Получение с загрузкой всех профилей
account = await account_repo.get_by_id_with_profiles(account_id)

# Создание из Telegram данных (создает все связанные профили автоматически)
account = await account_repo.create_from_telegram(
    telegram_id=123456,
    username="user",
    first_name="Name",
    last_name="Surname",
    language_code="ru",
)
```

### UserProfileRepository (NEW fields)

```python
from db.repositories import UserProfileRepository

# Получение профиля
profile = await profile_repo.get_by_account_id(account_id)

# Обновление с NEW полями (sex, address_mode)
await profile_repo.update_profile(
    account_id=account_id,
    display_name="Имя",
    age=25,
    sex="female",  # NEW: male/female/prefer_not_to_say
    address_mode="formal",  # NEW: formal/informal
    mark_complete=True,
)

# Свойства профиля
profile.sex_display  # "Мужской"/"Женский"/"Не указан"
profile.address_mode_display  # "На 'Вы'"/"На 'Ты'"
profile.effective_display_name  # Имя с fallback
profile.effective_age  # Возраст с fallback
```

### TherapistPreferenceRepository

```python
from db.repositories import TherapistPreferenceRepository

# Проверка завершения прескрининга
is_complete = await pref_repo.is_prescreening_complete(account_id)

# Обновление настроек
await pref_repo.update_preferences(
    account_id=account_id,
    therapist_name="Опора",
    therapist_gender="female",  # male/female
    therapist_traits=["empathetic", "calm"],
    mark_complete=True,
)

# Получение профиля для промптов
profile = pref.get_therapist_profile()
# Returns: {"name": "...", "gender": "...", "traits": [...]}
```

### ClinicalProfileRepository

```python
from db.repositories import ClinicalProfileRepository

# Получение клинической карточки
record = await clinical_repo.get_patient_record(account_id)
# Returns dict для промптов агентов

# Проверка заполненности
is_filled = await clinical_repo.is_card_filled(account_id)

# Обновление данных
await clinical_repo.update_clinical_data(
    account_id=account_id,
    mental_health_history="...",
    physical_health_history="...",
    current_problems="...",
    intake_hypothesis="...",
    intake_hypothesis_explanation="...",
)
```

### SessionRepository

```python
from db.repositories import SessionRepository

# Работа с сессиями (NEW: account_id вместо user_id)
session = await session_repo.create_session(
    account_id=account_id,
    session_number=1,
    therapy_type="CBT",
)

# Получение активной сессии
active = await session_repo.get_active_session(account_id)

# NEW: Получение всех сессий аккаунта
all_sessions = await session_repo.get_all_account_sessions(account_id)
```

### IntakeStateRepository (NEW)

```python
from db.repositories import IntakeStateRepository

# Создание состояния intake
state = await intake_repo.create_for_session(
    session_id=session_id,
    flow_phase="prescreening",
)

# Обновление фазы
await intake_repo.update_flow_phase(session_id, "therapy")

# Инкремент счетчика ходов
await intake_repo.increment_turns(session_id)

# Завершение intake
await intake_repo.mark_completed(session_id)

# Проверка завершения
is_completed = await intake_repo.is_intake_completed(session_id)
```

## Agent API

### SessionState (NEW fields)

```python
from agents.core import SessionState

state = SessionState(
    patient_id="123",
    session_id="123_1",
    # ... другие поля ...
    # NEW:
    patient_sex="female",  # male/female/prefer_not_to_say
    address_mode="formal",  # formal/informal
)

# Свойства для работы с address_mode
state.is_formal_address  # True если formal
state.is_informal_address  # True если informal
state.get_address_pronoun_you()  # "вы" или "ты"
state.get_address_pronoun_your()  # "ваш" или "твой"
```

### TherapistPrompts (NEW parameters)

```python
from agents.prompts import TherapistPrompts

# System message с address_mode
system_msg = TherapistPrompts.get_system_message(
    therapist_name="Опора",
    therapist_gender="female",
    therapist_traits=["empathetic"],
    address_mode="formal",  # NEW: formal/informal
)

# Response prompt с NEW полями
prompt = TherapistPrompts.get_response_prompt(
    patient_input="...",
    # ... другие параметры ...
    patient_sex="female",  # NEW
    address_mode="formal",  # NEW
)

# Приветствия с address_mode
greeting = TherapistPrompts.get_first_session_greeting(
    therapist_name="Опора",
    patient_display_name="Имя",
    language="ru",
    address_mode="formal",  # NEW
)

# Fallback с address_mode
fallback = TherapistPrompts.get_fallback_response(
    language="ru",
    address_mode="informal",  # NEW
)
```

### IntakePrompts (system / user split)

```python
from agents.prompts import IntakePrompts

# System: global static rules + session context (persona, prescreening, completion policy)
system_prompt = IntakePrompts.get_system_message(
    therapist_name="Опора",
    therapist_gender="female",
    therapist_styles=["business"],
    patient_name="Имя",
    patient_age=25,
    patient_sex="female",
    address_mode="formal",
    min_user_turns=6,
    required_fields=["current_problems", "mental_health_history"],
    max_user_turns=12,
)

# User: turn snapshot only (card, dialogue, active style, current message)
user_prompt = IntakePrompts.get_intake_turn_user_prompt(
    patient_message="...",
    current_card={...},
    current_user_turns=1,
    recent_dialogue=[{"role": "user", "content": "..."}],
    therapist_styles=["business"],
    therapist_name="Опора",
    max_user_turns=12,
)

# Deprecated alias — returns user_prompt only; use get_system_message + get_intake_turn_user_prompt
legacy_user = IntakePrompts.get_intake_turn_prompt(...)

# Fallback с address_mode
fallback = IntakePrompts.get_fallback_intake_response(
    patient_name="Имя",
    address_mode="informal",
)
```

## Service API

### DialogueService (Updated)

```python
from services import DialogueService

service = DialogueService()

# Старт сессии (NEW: использует новые репозитории)
greeting = await service.start_session(
    telegram_id=123456,
    username="user",
    first_name="Name",
    last_name="Surname",
    language_code="ru",
)

# Обработка сообщения (NEW: передает sex и address_mode в агенты)
result = await service.process_message(
    telegram_id=123456,
    text="Привет",
)

# Получение анкеты (NEW: включает sex и address_mode)
anket = await service.get_user_anket(telegram_id=123456)

# Получение сводки (NEW: включает sex)
summary = await service.get_patient_summary(telegram_id=123456)
```

## Telegram Handlers

### Prescreening Flow (NEW steps)

```python
from integrations.telegram.prescreening import (
    start_prescreening,
    handle_prescreening_text,
    start_prescreening_for_edit,
)

# Запуск прескрининга (теперь включает sex и address_mode)
await start_prescreening(message)

# Обработка текста внутри прескрининга
handled = await handle_prescreening_text(message)

# Редактирование анкеты (поддерживает все поля)
await start_prescreening_for_edit(message, user_id)
```

## Constants

### Доступные значения полей

```python
# Sex (profile.user_profiles.sex)
SEX_MALE = "male"
SEX_FEMALE = "female"
SEX_PREFER_NOT_TO_SAY = "prefer_not_to_say"

# Address Mode (profile.user_profiles.address_mode)
ADDRESS_FORMAL = "formal"    # "Вы"
ADDRESS_INFORMAL = "informal"  # "Ты"

# Therapist Gender (profile.therapist_preferences.therapist_gender)
GENDER_MALE = "male"
GENDER_FEMALE = "female"

# Flow Phase (therapy.intake_states.flow_phase)
PHASE_PRESCREENING = "prescreening"
PHASE_INTAKE = "intake"
PHASE_THERAPY = "therapy"
```
# Sandbox API Update

`POST /api/sandbox/sessions` accepts:

```json
{
  "name": "UI sandbox run",
  "start_phase": "prescreening",
  "prescreening_mode": "ai_generated",
  "manual_prescreening_profile": {
    "patient_name": "Мария",
    "patient_age": 29,
    "patient_sex": "female",
    "address_mode": "formal",
    "therapist_name": "Опора",
    "therapist_gender": "female",
    "therapist_styles": ["friendly", "soft"]
  },
  "ai_prescreening_seed": "Проверить тревожного пациента на этапе анкеты",
  "scenario_seed": "Рабочее выгорание и страх оценки",
  "patient_persona_source": "generated",
  "model_overrides": {}
}
```

Response includes:

```json
{
  "run_id": 1,
  "account_id": 10,
  "session_id": 20,
  "status": "active",
  "start_phase": "prescreening",
  "prescreening_mode": "ai_generated",
  "generated_prescreening_profile": {},
  "generated_scenario": {},
  "effective_model_config": {}
}
```

Allowed `start_phase` values: `prescreening`, `intake`, `therapy`.
Allowed `prescreening_mode` values: `manual`, `ai_generated`.
Allowed `patient_persona_source` values: `generated`, `manual`, `legacy_template`.
