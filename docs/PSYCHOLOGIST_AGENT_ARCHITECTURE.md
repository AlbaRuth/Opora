# Архитектура агента-психолога в Opora

## Назначение документа

Этот документ описывает именно систему "психолога" в `Opora`: какие в ней есть агенты и вспомогательные компоненты, за что они отвечают, на каких этапах вызываются, что хранится в базе, как устроены промпты и как проходит один пользовательский диалог от первого входа до терапевтической сессии.

Документ опирается на текущую реализацию в `agents/`, `services/`, `integrations/telegram/` и `db/`.

## Коротко о системе

`Opora` не является "роем" независимых LLM-агентов. Это оркестрируемая система с одним главным сервисом маршрутизации и несколькими специализированными агентными ролями:

1. `DialogueService` управляет жизненным циклом диалога и решает, какой агент должен быть вызван.
2. `IntakeAgent` собирает первичную клиническую карточку пациента.
3. `TherapistAgent` ведет основной терапевтический диалог.
4. `TherapistEvaluator` не общается с пользователем напрямую, а выполняет внутренние LLM-оценки для выбора стратегии, эмоции, памяти, стадии терапии и т.п.

Снаружи пользователь видит одного "психолога", но внутри система делит работу на:

- этап первичной настройки персоны и профиля (`prescreening`);
- этап первичного сбора клинической информации (`intake`);
- этап основной терапии (`therapy`);
- слой скрытого оценивания (`evaluator`) для принятия решений.

## Высокоуровневая схема

```text
Telegram user
   ->
Telegram handlers
   ->
DialogueService
   -> prescreening flow (wizard, без LLM)
   -> IntakeAgent (LLM, сбор карточки)
   -> TherapistAgent (LLM, терапевтический ответ)
        -> TherapistEvaluator (LLM, внутренние оценки)
   ->
PostgreSQL + Langfuse + logs
```

## Основные роли в системе

### 1. `DialogueService` — оркестратор

Это не LLM-агент, а главный координатор всей системы.

#### Ответственность

- создает и завершает сессии;
- загружает профиль пользователя и настройки "психолога";
- определяет текущую фазу процесса: `intake` или `therapy`;
- собирает `SessionState` для агентного слоя;
- сохраняет входящие и исходящие сообщения;
- переключает поток между `IntakeAgent` и `TherapistAgent`;
- обновляет `therapy_sessions`, `intake_states`, историю сообщений и метаданные.

#### Когда вызывается

`DialogueService` участвует почти всегда:

1. при `/start` вызывает `start_session()`;
2. после завершения прескрининга может тихо создать сессию через `create_session_silent()`;
3. на каждое обычное пользовательское сообщение вызывает `process_message()`;
4. по `/summary` отдает сжатую сводку клинической карточки;
5. по `/anket` отдает анкету/настройки;
6. по `/reset` удаляет весь пользовательский контур данных.

#### Почему это важно

Вся "агентность" в проекте статeless на уровне Python-объектов: текущее состояние не хранится внутри singleton-агента, а каждый раз восстанавливается из БД и укладывается в `SessionState`.

---

### 2. `IntakeAgent` — агент первичного клинического сбора

Это первый LLM-агент, который реально разговаривает с пользователем после заполнения прескрининга, если карточка пациента еще пустая.

#### Главная задача

Собрать и постепенно уточнить первичную клиническую картину:

- история психического здоровья;
- история физического здоровья;
- текущие проблемы и симптомы;
- предварительная intake-гипотеза;
- объяснение этой гипотезы.

#### Что делает

На каждом intake-ходе агент:

1. берет текущее сообщение пациента;
2. поднимаеущую карточку ит текз `clinical.clinical_profiles`;
3. подмешивает недавний контекст диалога;
4. отправляет LLM структурированный промпт;
5. ожидает JSON-ответ;
6. обновляет карточку;
7. определяет, завершен ли intake;
8. возвращает пользователю следующий вопрос/реплику.

#### Когда вызывается

`IntakeAgent.process_patient_input()` вызывается только тогда, когда:

- у пользователя есть активная сессия;
- `intake_states.flow_phase == "intake"`.

То есть последовательность такая:

1. пользователь проходит `prescreening`;
2. система создает сессию;
3. если карточка не заполнена и `INTAKE_ENABLED=true`, стартует `intake`;
4. каждый новый пользовательский текст идет в `IntakeAgent`;
5. после достижения полноты карточки или лимита ходов этап закрывается;
6. `flow_phase` переключается в `therapy`.

---

### 3. `TherapistAgent` — основной агент-психолог

Это главный пользовательский агент, который ведет терапевтический диалог.

#### Главная задача

Сформировать безопасный, эмпатичный и контекстный ответ психолога с учетом:

- текущего сообщения пациента;
- эмоции и интенсивности;
- текущего терапевтического подхода;
- стадии терапии;
- выбранной стратегии ответа;
- релевантной памяти прошлых сессий;
- персонализации психолога из анкеты.

#### Что делает

У него два ключевых сценария.

##### `start_new_session()`

Вызывается при старте терапевтической сессии и:

1. достает клиническую карточку;
2. собирает данные по прошлым сессиям;
3. запускает кросс-сессионную оценку через `TherapistEvaluator`;
4. выбирает/обновляет вид терапии;
5. формирует приветствие;
6. логирует стартовое решение в `decision_logs`.

##### `process_patient_input()`

Вызывается на каждом терапевтическом сообщении и:

1. увеличивает счетчик диалога;
2. просит `TherapistEvaluator` определить:
  - стоит ли завершать сессию;
  - есть ли сопротивление/уход от темы;
  - какая базовая эмоция и ее интенсивность;
  - нужна ли память прошлых разговоров;
  - какая стратегия ответа сейчас уместна;
  - какая стадия терапии актуальна;
3. собирает терапевтический промпт;
4. вызывает LLM для финального текста ответа;
5. логирует decision snapshot в `therapy.decision_logs`;
6. возвращает ответ и флаг завершения сессии.

#### Когда вызывается

`TherapistAgent` вызывается в двух местах:

1. `start_new_session()` — при старте новой therapy-сессии;
2. `process_patient_input()` — на каждом пользовательском сообщении в фазе `therapy`.

---

### 4. `TherapistEvaluator` — скрытый аналитический агент

Это внутренний LLM-агент. Он не пишет пользователю напрямую, а помогает `TherapistAgent` принимать решения.

#### Главная задача

Разложить терапевтическое решение на небольшие специализированные подзадачи.

#### Какие задачи он решает

- `evaluate_client_reaction()` — определяет сопротивление или уход от темы;
- `assess_emotion()` — определяет основную эмоцию и ее интенсивность;
- `update_response_strategy()` — выбирает стратегию ответа;
- `should_use_memory()` — решает, нужно ли подтягивать релевантную память прошлых разговоров;
- `should_end_session()` — определяет, хочет ли пользователь завершить сессию;
- `evaluate_therapy_progress()` — оценивает эффект прошлой терапии;
- `determine_treatment_stage()` — формирует описание текущей стадии терапии;
- `select_initial_therapy()` — выбирает стартовый терапевтический подход;
- `cross_session_evaluate()` — общий выбор терапии на старте новой сессии.

#### Когда вызывается

##### На старте therapy-сессии

- `TherapistAgent.start_new_session()`
-> `TherapistEvaluator.cross_session_evaluate()`
-> либо `select_initial_therapy()`, либо `evaluate_therapy_progress()`

##### На каждом терапевтическом сообщении

- `should_end_session()`
- `evaluate_client_reaction()`
- `assess_emotion()`
- `should_use_memory()`
- `determine_treatment_stage()` при необходимости
- `update_response_strategy()`

#### Почему это важно

Архитектурно это превращает одного "умного психолога" в композицию:

- отдельный агент-генератор ответа (`TherapistAgent`);
- отдельный агент-оценщик (`TherapistEvaluator`).

Так система лучше логирует reasoning-этапы и может хранить decision trail.

## Этапы жизненного цикла пользователя

### Этап 1. `prescreening`

Это не LLM-этап, а Telegram wizard.

#### Что собирается

- имя психолога;
- пол психолога;
- имя/псевдоним пациента;
- возраст;
- пол пациента;
- стиль обращения (`formal`/`informal`, то есть "Вы"/"Ты");
- стили общения психолога:
  - `friendly`;
  - `soft`;
  - `business`;
  - `motivating`.

#### Где хранится

- временное состояние wizard хранится в памяти процесса в `_prescreening_states`;
- после завершения данные записываются в PostgreSQL.

#### Что важно

Это единственная часть системы, где состояние временно хранится in-memory, а не в БД. В комментариях к коду прямо указано, что в production это при желании можно заменить на Redis или отдельное хранилище.

---

### Этап 2. `intake`

Это этап первичного клинического сбора.

#### Цель

Не лечить и не давать советы, а собрать достаточную информацию для продолжения терапии.

#### Критерии завершения

Intake считается завершенным, если выполнено одно из условий:

1. заполнены обязательные поля карточки;
2. достигнут минимум пользовательских ходов;
3. не осталось обязательных пропусков;
4. либо достигнут жесткий максимум ходов, и тогда система завершает intake даже с пометкой `initial_info_insufficient`.

#### Что происходит на выходе

- `intake_states.completed_at` заполняется;
- `flow_phase` переводится в `therapy`;
- пользователю отправляется уведомление о завершении intake;
- дальше сообщения идут уже в `TherapistAgent`.

---

### Этап 3. `therapy`

Это основной пользовательский режим.

#### Цель

Вести устойчивый терапевтический диалог с учетом:

- истории текущей сессии;
- прошлых сессий;
- персонализации тона;
- текущей стратегии ответа;
- фазы терапии;
- контекста клинической карточки.

#### Особенности

- на каждый ход пациента система пишет в БД и само сообщение пациента, и ответ "психолога";
- сессия может быть завершена автоматически, если пользователь явно завершает разговор.

## Что именно хранится в системе

Система использует нормализованную PostgreSQL-схему с разделением по доменам.

### 1. `identity.accounts`

Корневая сущность пользователя.

Хранит:

- `telegram_id`;
- `username`;
- `first_name`;
- `last_name`;
- `language_code`.

Это "точка сборки" для всех остальных сущностей пользователя.

### 2. `profile.user_profiles`

Пользовательский профиль пациента.

Хранит:

- `display_name`;
- `age`;
- `sex`;
- `address_mode`;
- признаки завершенности профиля;
- legacy-поля для совместимости миграций.

Используется для персонализации ответа и отображения анкеты.

### 3. `profile.therapist_preferences`

Настройки персоны "психолога".

Хранит:

- `therapist_name`;
- `therapist_gender`;
- `therapist_traits` — фактически список выбранных `styles`;
- `prescreening_completed_at`.

Из этой таблицы агент получает "маску" психолога: как его зовут, в каком роде говорить, какие стили общения допустимы.

### 4. `clinical.clinical_profiles`

Клиническая карточка пациента.

Хранит:

- `mental_health_history`;
- `physical_health_history`;
- `current_problems`;
- `intake_hypothesis`;
- `intake_hypothesis_explanation`;
- `initial_info_insufficient`.

Это главный долговременный clinical context для дальнейшей терапии.

### 5. `therapy.therapy_sessions`

Карточка одной терапевтической сессии.

Хранит:

- номер сессии;
- текущий тип терапии;
- причину выбора терапии;
- счетчик реплик;
- активность/завершенность;
- `current_stage`.

### 6. `therapy.intake_states`

Состояние intake-потока в рамках сессии.

Хранит:

- `flow_phase`;
- `user_turn_count`;
- `completed_at`.

Это отдельное process-state хранилище, чтобы не смешивать intake-процесс и собственно терапию.

### 7. `therapy.messages`

Полная история диалога.

Хранит:

- роль: `patient` или `doctor`;
- текст сообщения;
- номер сообщения;
- опционально эмоцию и интенсивность.

Используется для:

- восстановления контекста текущей сессии;
- памяти последних сообщений;
- кросс-сессионного анализа;
- аудита истории диалога.

### 8. `therapy.decision_logs`

Лог терапевтических решений.

Хранит для каждого ответа:

- нужно ли было использовать память;
- было ли сопротивление;
- текущую терапию;
- текущую стадию;
- эмоцию и ее интенсивность;
- выбранную стратегию ответа;
- текстовое описание стратегии;
- полный `decision_snapshot` в JSON.

Это главный audit trail для объяснения, почему агент ответил именно так.

### 9. `observability.agent_logs`

Логи всех LLM-вызовов.

Хранит:

- тип агента (`intake`, `therapist`, `evaluator`);
- задачу (`task_name`);
- модель;
- температуру;
- лимиты токенов;
- prompt;
- response;
- latency;
- token usage;
- success/error;
- `langfuse_trace_id`;
- дополнительные metadata.

Это слой наблюдаемости, а не бизнес-данных.

## Что НЕ хранится в памяти агента

Система намеренно спроектирована как stateless orchestration.

То есть:

- `TherapistAgent` не хранит текущее состояние пользователя между запросами;
- `IntakeAgent` не держит "живую сессию" внутри объекта;
- состояние восстанавливается через `SessionState`, который собирается заново из БД перед каждым ходом.

Исключение:

- временный Telegram prescreening wizard хранится в `_prescreening_states`.

## `SessionState` — runtime-контракт между сервисом и агентом

`SessionState` — это компактный DTO, через который `DialogueService` передает состояние агентам.

Он включает:

- `patient_id`;
- `session_id`;
- `session_db_id`;
- `dialog_count`;
- `session_counter`;
- `current_therapy`;
- `current_stage`;
- `flow_phase`;
- `intake_user_turns`;
- `therapist_name`;
- `therapist_gender`;
- `therapist_styles`;
- `patient_display_name`;
- `patient_age`;
- `patient_sex`;
- `address_mode`.

То есть агентный слой не ходит сам за всеми пользовательскими настройками по кускам; он получает уже собранный state contract.

## Как устроены промпты

### Общий принцип

Система использует несколько наборов промптов:

1. `TherapistPrompts` — генерация пользовательского ответа психолога;
2. `IntakePrompts` — сбор карточки на этапе intake (`get_system_message` = global + session static; `get_intake_turn_user_prompt` = card, dialogue, message per turn);
3. `EvaluatorPrompts` — скрытые аналитические задачи.

### 1. Промпты терапевта

Наиболее важные особенности:

- system message описывает терапевтические принципы;
- в system message встроены границы роли: не давать прямые советы, не обещать исход, не быть "другом";
- стиль общения выбирается из доступных `styles`;
- можно динамически переключать active style по контексту;
- жестко задается `address_mode` ("ты" или "вы");
- ответ должен быть на том же языке, что и пользователь;
- ответ ограничен по длине;
- в prompt передается история последних сообщений, чтобы не повторять один и тот же паттерн фраз.

### 2. Промпты intake

Здесь фокус другой:

- требование вернуть JSON строго заданной схемы;
- явные правила, когда обновлять карточку, а когда не обновлять;
- требование формировать только предварительную гипотезу, а не диагноз;
- анти-повторные правила для пользовательской фразы;
- обязательность открытого вопроса;
- правило "один вопрос за ответ";
- учет предыдущего диалога intake.

Фактически `IntakeAgent` использует LLM как структурированный extractor + собеседник.

### 3. Промпты evaluator

Это набор очень узких служебных промптов:

- эмоция;
- стратегия;
- сопротивление;
- конец сессии;
- память;
- стадия лечения;
- выбор терапии;
- оценка эффекта прошлой сессии.

Важная особенность: evaluator обычно возвращает или JSON, или короткий строгий ответ (`True`/`False`, название стратегии, краткий текст).

#### Где они хранятся

Все шаблоны evaluator-промптов лежат в `agents/prompts/evaluator_prompts.py`, а вызываются из `agents/evaluators/therapist_evaluator.py`.

Архитектурно это выглядит так:

1. `TherapistAgent` или `DialogueService` инициирует этап принятия решения.
2. `TherapistEvaluator` выбирает нужную аналитическую подзадачу.
3. Для этой подзадачи берется соответствующий шаблон из `EvaluatorPrompts`.
4. В шаблон подставляются конкретные данные текущего пользователя, сессии или истории диалога.
5. Модель возвращает либо структурированный JSON, либо короткий строгий ответ.
6. `TherapistEvaluator` парсит результат и отдает его обратно в `TherapistAgent`.
7. `TherapistAgent` использует результат при сборке финального терапевтического ответа.

Ниже подробно разобран каждый evaluator prompt.

#### Общий system prompt evaluator

Для всех evaluator-задач используется общий системный промпт:

- `EVALUATOR_SYSTEM = "You are a professional psychological counselor."`

Это минимальный system layer, который задает модели роль профессионального психологического консультанта, но не перегружает каждую подзадачу лишними общими инструкциями. Вся специализация уже задается внутри конкретного task prompt.

Такой подход делает evaluator-промпты:

- изолированными друг от друга;
- проще тестируемыми;
- более предсказуемыми по формату ответа;
- удобными для логирования и последующего аудита.

### 3.1. Промпт оценки эмоции

#### Где хранится

- `EvaluatorPrompts.EMOTION_ASSESSMENT`

#### Кто вызывает

- `TherapistEvaluator.assess_emotion()`

#### Входные данные

Промпт получает:

- `patient_input` — текущее сообщение пациента.

#### Что должен сделать

Модель должна:

1. выбрать одну основную эмоцию из фиксированного списка;
2. оценить ее интенсивность по шкале от `0.0` до `1.0`;
3. при необходимости распознать "замаскированную" эмоцию.

#### Почему это важно

Это один из самых критичных evaluator-промптов, потому что от него дальше зависят:

- выбор стратегии ответа;
- тон финальной реплики;
- выбор активного стиля общения в `TherapistPrompts`;
- степень мягкости или структурности ответа.

Если эмоция определена как сильная и негативная, система склоняется к более мягкому, отражающему и поддерживающему ответу.

#### Особенности промпта

В текущем шаблоне есть важный акцент не только на "поверхностной" эмоции, но и на скрытых состояниях:

- злость может маскировать уязвимость, стыд или страх;
- юмор может маскировать тревогу;
- рационализация может маскировать эмоциональную перегрузку;
- уход в "не знаю" может маскировать беспомощность или стыд.

Это означает, что evaluator не просто делает keyword matching, а должен попытаться восстановить более глубинное чувство.

#### Формат выхода

Строгий JSON:

```json
{
  "primary_emotion": "str",
  "emotional_intensity": "float"
}
```

#### Оригинальный шаблон промпта

```text
##Role:
You are a professional and empathetic psychological counselor.
Identify the primary emotion and assess its intensity in the patient's words.
##Criteria:
The patient words: {patient_input}.
1. primary_emotion:
The primary emotion is the most intense one in the patient words.
You can only choose one from the list: ["joy", "sadness", "anger", "fear", "disgust", "surprise", "trust","anticipation"].

IMPORTANT - Recognizing Masked Emotions:
- Sometimes patients express one emotion while feeling another (e.g., anger masking hurt, humor masking anxiety).
- Look for underlying feelings beneath surface expressions:
  * Anger may mask: hurt, fear, vulnerability, shame
  * Humor/jokes may mask: anxiety, discomfort, pain, fear
  * Intellectual analysis may mask: emotional overwhelm, sadness, fear
  * Withdrawal/"I don't know" may mask: fear, shame, helplessness
- If you detect a masked emotion, identify the UNDERLYING feeling as primary_emotion.
- Trust your clinical intuition about what the patient is really experiencing beneath their words.

2. emotional_intensity:
The intensity of the emotion you identified above (a float number from 0 to 1, where 0 indicates no emotion and 1 indicates very intense emotion). Please retain one decimal place.
- 0.0-0.3: Low intensity, barely present
- 0.4-0.6: Moderate intensity, clearly present
- 0.7-0.8: High intensity, significantly impacting
- 0.9-1.0: Very intense, overwhelming or crisis-level

##Constraints:
Return your answer strictly in JSON format, like this:
{
   "primary_emotion": "str",
   "emotional_intensity": "float"
}
```

#### Как результат используется дальше

Результат идет:

- в `decision_logs`;
- в `update_response_strategy()`;
- в `_generate_response()` у `TherapistAgent`.

Именно этот prompt определяет, будет ли финальный ответ:

- мягче;
- структурнее;
- более валидирующим;
- более исследовательским.

### 3.2. Промпт выбора стратегии ответа

#### Где хранится

- `EvaluatorPrompts.get_strategy_prompt(...)`

#### Кто вызывает

- `TherapistEvaluator.update_response_strategy()`

#### Входные данные

Промпт получает:

- `patient_input`;
- `primary_emotion`;
- `emotional_intensity`;
- `is_rejecting`;
- `session_strategy_memory`.

#### Что должен сделать

Модель должна выбрать ровно одну стратегию ответа и коротко объяснить, как терапевту ей следовать в этом ходе.

То есть на выходе evaluator определяет не сам текст ответа, а "режим работы" для основного терапевтического агента.

#### Какие стратегии доступны

Шаблон перечисляет допустимые стратегии, среди которых:

- `Interpretation`;
- `Gentle Challenge`;
- `Invite to Take New Perspectives`;
- `Invite to Explore New Actions`;
- `Empathic Reflection`;
- `Restatement`;
- `Clarification`;
- `Validation`;
- `Inquiring Subjective Information`;
- `Summarization`.

#### Что важно архитектурно

Внутри промпта специально удалены или запрещены нежелательные терапевтические ходы:

- self-disclosure;
- confrontation в жесткой форме;
- advice-giving;
- пустое reassurance;
- директивность;
- "объективный допрос" вместо исследования субъективного опыта.

То есть prompt сам по себе выступает как слой safety/policy для терапевтической логики.

#### Почему этот prompt особенно важен

Именно он связывает аналитический слой с генеративным. Его результат задает для `TherapistAgent`:

- какой тип отклика сейчас нужен;
- какой терапевтический микроприем применять;
- насколько исследовать, валидировать, отражать или мягко переосмыслять.

По сути:

- evaluator решает "как отвечать";
- therapist agent решает "какими словами это сказать".

#### Формат выхода

Строгий JSON:

```json
{
  "strategy": "",
  "strategy_text": ""
}
```

#### Оригинальный шаблон промпта

```text
##Role:
You are a professional and empathetic psychological counselor.
Choose only one response strategy and provide the psychological counselor a response guidance.
##Requirements:
1. Choose a response strategy as "strategy".
*Reference Information:
  - patient's current words: {patient_input}
  - patient's primary emotion: {primary_emotion}
  - patient's emotional intensity: {emotional_intensity}
  - whether the patient is rejecting or deviate from the topic: {"Yes" if is_rejecting else "No"}
*Rules:
  Determine the patient's current attitude first and then choose a suitable strategy based on the information above. The attitude you judged must be strictly positive or negative.
  * If patient attitude is "positive", then you can only strictly choose one suitable strategy from options A to D.
  * If patient attitude is "negative", then you can only strictly choose one suitable strategy from options E to J.
  [Below are the options]:
    A. Interpretation (The counselor conducts in-depth analysis and explanation of the patient's words and actions, helping the patient view problems from different perspectives. Use sparingly and only when client shows readiness.)
    B. Gentle Challenge (The counselor gently invites the patient to consider alternative viewpoints or notice patterns, WITHOUT being confrontational or judgmental. The tone is curious, not corrective.)
    C. Invite to Take New Perspectives (The counselor guides clients to view problems from different perspectives and broaden their thinking.)
    D. Invite to Explore New Actions (The counselor encourages the patient to consider new behaviors or methods, but the patient always chooses what feels right for them. No pressure.)
    E. Empathic Reflection (PRIORITY strategy for high emotional intensity. The counselor identifies, acknowledges, and reflects patient's emotions without judgment or problem-solving. Helps patient feel understood.)
    F. Restatement (The counselor repeats what the patient says in their own words to confirm understanding and show they are listening.)
    G. Clarification (The counselor asks gentle questions to clarify what the patient means, without interrogating or assuming.)
    H. Validation (The counselor acknowledges the legitimacy of patient's feelings and experiences, confirming that their reactions make sense given their context.)
    I. Inquiring Subjective Information (The counselor asks open-ended questions about thoughts, feelings, and expectations to understand the patient's inner world. Focus on "how" and "what", not "why".)
    J. Summarization (The counselor briefly summarizes key points from what the patient shared to help organize thoughts and show engagement.)
  [IMPORTANT NOTES]:
  - Empathic Reflection is the DEFAULT and PRIORITY strategy when emotional intensity > 0.6 or when emotions are negative (sadness, anxiety, fear, anger).
  - Self-disclosure is REMOVED - the counselor must NEVER share personal experiences or feelings. This maintains professional boundaries.
  - Confrontation is REMOVED - replaced with Gentle Challenge which is non-judgmental.
  - Answer/Advice-giving is REMOVED - the counselor does NOT give direct advice or tell the patient what to do.
  - Minimal Encouragement is REMOVED - it can feel dismissive; use Empathic Reflection or Validation instead.
  - Affirmation and Reassurance is REMOVED - empty reassurance violates therapeutic boundaries; use Validation instead.
  - Inquiring Objective Information is REMOVED - focus on subjective experience, not facts.
  [Notice]:
  Only return the strategy name of your selected option. For example, if you choose "A. Interpretation", then just return "Interpretation".
2. Based on your strategy, generate a concise corresponding response strategy text of no more than 30 words to precisely guide the psychological counselor's response as "strategy_text".
3. Make strategies more diverse, don't always stick to a single strategy.
  In this session, you have used the following strategies: {session_strategy_memory}. Please try different strategies as much as possible as long as they are reasonable.
  PRIORITY: Use Empathic Reflection more frequently than other strategies, especially for emotional content.
##Constraints:
Strictly output the substantive content of your choice, excluding any option identifiers (such as 'A.', 'B.', 'C.', etc.) and things in parentheses.
Return your answer strictly in JSON format, like this:
{
   "strategy": "",
   "strategy_text": ""
}
```

#### Как результат используется дальше

Значения `strategy` и `strategy_text` передаются в `TherapistPrompts.get_response_prompt(...)` и становятся частью контекста для финальной генерации ответа.

Также они попадают в `decision_logs`, чтобы потом можно было посмотреть, какая именно стратегия была выбрана на каждом ходе.

### 3.3. Промпт оценки сопротивления или ухода от темы

#### Где хранится

- `EvaluatorPrompts.CLIENT_REACTION`

#### Кто вызывает

- `TherapistEvaluator.evaluate_client_reaction()`

#### Входные данные

- `patient_input`

#### Что должен сделать

Определить, есть ли в текущем сообщении:

- сопротивление терапевтическому процессу;
- отказ продолжать обсуждение;
- заметный уход в несвязанный topic shift.

#### Что именно понимается под сопротивлением

В рамках текущего prompt resistance включает:

- прямой отказ отвечать или продолжать;
- явное раздражение или нетерпение;
- отказ от текущей темы;
- сильное отклонение в нерелевантную область.

#### Почему это важно

Если evaluator видит сопротивление, то дальше стратегия ответа обычно должна стать:

- менее продавливающей;
- менее интерпретативной;
- более аккуратной;
- ориентированной на clarification, validation или empathic reflection.

Это снижает риск, что терапевтический агент начнет давить на пользователя не в том моменте.

#### Формат выхода

Строгий boolean:

- `True`
- `False`

#### Оригинальный шаблон промпта

```text
##Role:
You are a professional and empathetic psychological counselor. 
##Task:
Based on the patient input: {patient_input}, determine whether the patient shows resistance or has significantly deviated from the consultation topic.
##Criteria:
Below are just some main criteria (other reasonable standards can also be referred to).
1. indicators that clearly reject the current topic:
  - directly reject the consultant's advice or questions
  - show obvious impatience
  - express a direct refusal or unwillingness to continue the conversation
2. indicators that significantly deviate from the consultation topic:
  - suddenly introducing a completely unrelated new topic
  - the response content has no logical connection with the current discussion issue
  - using expressions that obviously shift the topic 
##Constraints:
Directly output a Boolean value True or False.
```

#### Как результат используется дальше

Результат подается в `get_strategy_prompt(...)` и влияет на выбор response strategy.

Также он логируется в `decision_logs` как один из ключевых признаков текущего состояния диалога.

### 3.4. Промпт определения конца сессии

#### Где хранится

- `EvaluatorPrompts.SESSION_END`

#### Кто вызывает

- `TherapistEvaluator.should_end_session()`

#### Входные данные

- `patient_input`

#### Что должен сделать

Определить, выражает ли пользователь явное намерение завершить разговор.

#### Логика задачи

Этот prompt не пытается "угадывать усталость" или абстрактное снижение интереса. Он намеренно узкий и консервативный:

- завершать сессию только при прямом или достаточно явном сигнале;
- не завершать по косвенным признакам;
- не путать эмоциональный спад с желанием закончить разговор.

#### Почему это важно

Слишком агрессивное завершение сессии было бы вредным для UX и терапевтической связности. Поэтому prompt сформулирован строго:

- только clear intention;
- только `True` или `False`;
- без дополнительных пояснений.

#### Формат выхода

Строгий boolean:

- `True`
- `False`

#### Оригинальный шаблон промпта

```text
##Role:
You are a professional and empathetic psychological counselor. 
##Requirements:
Your task is to strictly judge whether the current session should be ended based on the patient's current words: {patient_input}.
Only when the patient expresses a clear intention to end (such as saying "goodbye", "that's all for today", "we'll talk next time", etc.), return True. Otherwise return False.
##Constraints:
Strictly output a Boolean value True or False.
```

#### Как результат используется дальше

Если возвращается `True`, то:

1. `TherapistAgent` формирует завершающий ответ;
2. `DialogueService` после отправки ответа закрывает активную сессию через `session_repo.end_session(...)`.

### 3.5. Промпт определения необходимости памяти

#### Где хранится

- `EvaluatorPrompts.MEMORY_USAGE`

#### Кто вызывает

- `TherapistEvaluator.should_use_memory()`

#### Входные данные

Промпт получает:

- `all_dialogs` — исторические диалоги по прошлым сессиям;
- `patient_input` — текущее сообщение пациента.

#### Что должен сделать

Определить, нужно ли для текущего ответа реально опираться на историческую память.

Если связь с историей есть, модель должна вернуть краткую релевантную выжимку. Если связи нет, должна вернуть стандартную фразу, что память не требуется.

#### Почему этот prompt критичен

Он решает сразу две задачи:

1. не тащить лишний исторический контекст в каждый ответ;
2. не терять важные повторяющиеся темы, если пациент возвращается к ним спустя время.

То есть это prompt на selective recall, а не на полную суммаризацию истории.

#### Ограничение логики

Внутри шаблона зашито важное правило:

- память используется только если исторический материал явно связан с текущими словами пациента;
- при этом связь должна быть не слишком "дальней" или натянутой.

Это снижает риск ложной персонализации, когда агент начинает неуместно ссылаться на старые разговоры.

#### Формат выхода

Не JSON, а обычный короткий текст:

- либо краткая выжимка релевантной исторической памяти;
- либо строка `No need to consider historical conversation memory`.

#### Оригинальный шаблон промпта

```text
##Role:
You are a professional and empathetic psychological counselor. 
##Requirements:
Please determine if it is necessary to refer to the historical conversations to respond to the patient's current words.
  - historical conversations: {all_dialogs}
  - patient's current words: {patient_input}
Only when you can find places in the historical conversations that are clearly related to the content of the patient's current words, and the places are not too far away from the current conversation, is it necessary to refer to history.
  * If reference is needed:
    Summarize relevant historical content in no more than 500 words. Just directly return a concise and accurate summary.
  * If no reference is needed:
    Directly return the sentence 'No need to consider historical conversation memory'.
##Constraints:
Directly output your answer in Russian. Do not include any other analysis or explanation.
```

#### Как результат используется дальше

Этот результат напрямую передается в `TherapistPrompts.get_response_prompt(...)` как `memory_result`.

То есть финальный терапевтический агент получает уже не всю историю сессий, а специально отфильтрованный memory summary.

### 3.6. Промпт определения стадии лечения

#### Где хранится

- `EvaluatorPrompts.TREATMENT_STAGE`

#### Кто вызывает

- `TherapistEvaluator.determine_treatment_stage()`

#### Входные данные

Промпт получает:

- `current_therapy`;
- `all_dialogs`.

#### Что должен сделать

Сформировать компактное текстовое описание того:

- что уже было сделано в терапии;
- на какой стадии находится работа;
- куда логично двигаться дальше.

#### Что важно понимать

Это не label classification вроде `"early_stage"` или `"middle_stage"`. В текущей реализации stage хранится как свободный аналитический текст.

То есть `current_stage` в Opora — это не enum, а краткая narrative summary терапевтического этапа.

#### Почему это полезно

Это позволяет не терять continuity между сессиями:

- на старте нового ответа у терапевта есть ощущение, где находится работа;
- можно избегать резких перескоков между стилями и задачами;
- проще логировать progression терапии.

#### Формат выхода

Свободный короткий абзац, без JSON.

#### Оригинальный шаблон промпта

```text
##Role:
You are a professional and empathetic psychological counselor. 
##Requirements:
Provide an analysis of the current stage of treatment. The content of your analysis includes summarizing the completed treatment content and pointing out how to continue treatment next time.
Your analysis should be comprehensive and concise in no more than 80 words.
You also should refer to the two relevant information below:
  - current therapy: {current_therapy}
  - all history dialogs: {all_dialogs}
##Constraints:
Integrate your analysis into a fluent paragraph, without giving it in segments or sections.
Directly output your analysis content. Do not provide any explanation.
```

#### Как результат используется дальше

Возвращаемое значение:

- сохраняется в `therapy_sessions.current_stage`;
- включается в context для `TherapistPrompts.get_response_prompt(...)`;
- логируется в `decision_logs`.

### 3.7. Промпт выбора стартовой терапии

#### Где хранится

- `EvaluatorPrompts.INITIAL_THERAPY`

#### Кто вызывает

- `TherapistEvaluator.select_initial_therapy()`

#### Когда используется

Только на первой сессии, когда у пользователя еще нет прошлых терапевтических разговоров.

#### Входные данные

- `medical_record`

Это сериализованная clinical card, собранная из профиля пациента:

- возраст;
- имя/псевдоним;
- пол;
- история психического здоровья;
- история физического здоровья;
- текущие проблемы;
- intake-гипотеза;
- объяснение intake-гипотезы.

#### Что должен сделать

Рекомендовать подходящую терапию или комбинацию из двух терапий максимум.

#### Почему это важно

Это точка, где intake-данные впервые превращаются в operational therapeutic setup.

То есть:

- intake собирает материал;
- evaluator превращает этот материал в рабочий терапевтический подход;
- therapist agent дальше разговаривает уже с учетом выбранной терапии.

#### Формат выхода

Короткая строка с названием терапии без объяснений.

Примерно в духе:

- `cognitive-behavioral therapy`
- `acceptance and commitment therapy + cognitive-behavioral therapy`

#### Оригинальный шаблон промпта

```text
##Role:
You are a professional and empathetic psychological counselor. 
##Skills:
Please recommend a suitable psychological treatment therapy based on the patient medical record: {medical_record}.
It can be a single therapy or a reasonable combination therapy. Just use ' + ' to separate different therapy, but no more than two therapies.
##Constraints:
Please directly output the professional terminology of the therapy name without explanation or additional text.
```

#### Как результат используется дальше

Значение уходит в:

- `TherapistEvaluator.cross_session_evaluate()`;
- затем в `TherapistAgent.start_new_session()`;
- затем сохраняется в `therapy_sessions.therapy_type`.

### 3.8. Промпт оценки эффекта прошлой сессии

#### Где хранится

- `EvaluatorPrompts.THERAPY_PROGRESS`

#### Кто вызывает

- `TherapistEvaluator.evaluate_therapy_progress()`

#### Когда используется

Используется не на первой сессии, а при старте новой сессии, когда у пользователя уже есть история предыдущих терапевтических встреч.

#### Входные данные

Промпт получает:

- `last_therapy` — какая терапия использовалась в прошлой сессии;
- `last_dialogs` — полный диалог прошлой сессии.

#### Что должен сделать

Ответить на два вопроса:

1. дала ли прошлосессионная терапия терапевтический эффект;
2. стоит ли сохранить текущую терапию или сменить ее.

#### Почему это важно

Это механизм межсессионной адаптации. Он позволяет системе не "застывать" в одном therapy type навсегда.

Именно этот prompt отвечает за эволюцию therapeutic plan от сессии к сессии.

#### Формат выхода

Строгий JSON:

```json
{
  "new_therapy": "",
  "reason": ""
}
```

#### Оригинальный шаблон промпта

```text
##Role:
You are a professional and empathetic psychological counselor. 
Determine new therapy for the new session and provide short reason for your decision.
##Skills:
1. Determine "new_therapy".
Evaluate whether the last conversation had a therapeutic effect based on the therapy used in the last session and the conversation record of the last session provided below. If there is no therapeutic effect, then change the last therapy. If there is therapeutic effect, then stick to the last therapy. You only need to output a standard therapy name as "new_therapy".
It can be a single therapy or a reasonable combination therapy. Just use ' + ' to separate different therapy, but no more than two therapies.
Please directly output the professional terminology of the therapy name without explanation or additional text.
  - the therapy used in the last session: {last_therapy}
  - the conversation record of the last session: {last_dialogs}
2. Give some reason about your decision on "new_therapy".
  - The reason should not exceed 50 words.
##Constraints:
Return your answer strictly in JSON format, like this:
{
   "new_therapy": "",         
   "reason": "" 
}
```

#### Как результат используется дальше

Результат попадает в `cross_session_evaluate()`, после чего:

- либо сохраняется прежняя терапия;
- либо назначается новая;
- в `therapy_sessions.therapy_reason` сохраняется объяснение выбора.

### 3.9. Как evaluator-промпты работают вместе

Если смотреть не по отдельности, а как на единый decision pipeline, последовательность такая:

#### На старте новой сессии

1. Если это первая сессия:
   - используется `INITIAL_THERAPY`.
2. Если это не первая сессия:
   - используется `THERAPY_PROGRESS`.
3. При необходимости формируется или обновляется `current_therapy`.

#### На каждом пользовательском сообщении в therapy

1. `SESSION_END` отвечает на вопрос, не пора ли завершать диалог.
2. `CLIENT_REACTION` определяет сопротивление или уход от темы.
3. `EMOTION_ASSESSMENT` определяет эмоциональное состояние.
4. `MEMORY_USAGE` решает, нужно ли поднимать релевантную историю.
5. `TREATMENT_STAGE` уточняет, где находится терапевтический процесс.
6. `get_strategy_prompt(...)` выбирает response strategy.
7. Уже после этого `TherapistAgent` генерирует финальный текст.

Иными словами, `TherapistEvaluator` не пишет ответ пользователю, а подготавливает шесть аналитических "опорных точек", на которых строится финальная терапевтическая реплика.

### 3.10. Почему evaluator вынесен в отдельный слой

Отдельный evaluator нужен не только ради красоты архитектуры, а ради четырех практических свойств:

#### 1. Декомпозиция сложного решения

Один большой prompt "сразу обо всем" был бы хуже:

- сложнее дебажить;
- сложнее логировать;
- сложнее валидировать;
- выше риск нестабильных ответов.

#### 2. Аудит и explainability

Можно отдельно посмотреть:

- какую эмоцию увидела система;
- почему выбрала именно эту стратегию;
- почему решила поднять память;
- почему сменила терапию.

#### 3. Управляемость качества

Каждый evaluator prompt можно отдельно дорабатывать:

- ужесточать формат;
- улучшать safety;
- менять критерии;
- сравнивать качество на тестовых примерах.

#### 4. Стабильность финальной генерации

`TherapistAgent` получает уже структурированные промежуточные решения и не должен "на лету" сам выводить все эти уровни анализа в одном генеративном акте.

Это делает итоговый ответ более консистентным и управляемым.

## Как используется персонализация психолога

Пользователь в прескрининге настраивает не только свой профиль, но и "персону" психолога.

### Что влияет на ответы

- имя психолога;
- пол психолога;
- набор стилей общения;
- стиль обращения к пользователю;
- имя пациента;
- возраст;
- пол пациента.

### Как это влияет на генерацию

#### Имя психолога

Подставляется в greeting и в prompts как display persona.

#### Пол психолога

Используется для согласования русскоязычных формулировок и приветствий.

#### `address_mode`

Жестко влияет на грамматику:

- `formal` -> "вы", "вас", "ваш", "расскажите";
- `informal` -> "ты", "тебя", "твой", "расскажи".

#### `therapist_styles`

Определяет допустимые стили речи:

- `friendly` — теплее и контактнее;
- `soft` — мягче для тревоги и боли;
- `business` — структурнее для фактов и паттернов;
- `motivating` — акцент на ресурсах и изменениях.

И в `TherapistPrompts`, и в `IntakePrompts` есть логика выбора активного стиля для конкретного ответа.

## Как проходит один пользовательский ход

### Сценарий: обычное сообщение в фазе `therapy`

1. Telegram handler принимает текст.
2. `DialogueService.process_message()` проверяет пользователя и активную сессию.
3. Сервис берет advisory lock на сессию.
4. Сообщение пациента сохраняется в `therapy.messages`.
5. Собирается `SessionState`.
6. Вызывается `TherapistAgent.process_patient_input()`.
7. Внутри него последовательно вызываются методы `TherapistEvaluator`.
8. Формируется финальный prompt для ответа.
9. Через `OpenRouterClient` вызывается LLM.
10. Результат логируется в `observability.agent_logs`.
11. Decision snapshot логируется в `therapy.decision_logs`.
12. Ответ врача сохраняется в `therapy.messages`.
13. Обновляются `dialog_count`, `current_stage`, `therapy_type`.
14. При необходимости сессия закрывается.
15. Ответ уходит пользователю в Telegram.

### Сценарий: обычное сообщение в фазе `intake`

1. Telegram handler принимает текст.
2. `DialogueService.process_message()` видит `flow_phase == "intake"`.
3. Сообщение пациента сохраняется.
4. Вызывается `IntakeAgent.process_patient_input()`.
5. Агент получает карточку и недавний контекст.
6. LLM возвращает JSON с обновлениями карточки и репликой пациенту.
7. Карточка обновляется в `clinical_profiles`.
8. Увеличивается `user_turn_count`.
9. При необходимости `intake_states` помечается завершенным.
10. Пользователь получает следующий intake-вопрос или сообщение о переходе к терапии.

## Наблюдаемость и аудит

В системе есть два разных уровня прозрачности.

### 1. Business reasoning trail

Это `therapy.decision_logs`.

Он нужен, чтобы понимать:

- какую эмоцию увидел агент;
- какую стратегию выбрал;
- обращался ли к памяти;
- какая стадия терапии была определена.

### 2. LLM observability

Это `observability.agent_logs` плюс Langfuse.

Он нужен, чтобы видеть:

- какой prompt ушел в модель;
- какой ответ вернулся;
- какая была модель;
- сколько заняло времени;
- сколько ушло токенов;
- какой trace связан с этим вызовом.

## Конфигурация через `.env`

Основные блоки конфигурации:

### Инфраструктура

- `DATABASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `OPENROUTER_*`
- `LANGFUSE_*`

### Therapist agent

- `LLM_THERAPIST_MODEL`
- `LLM_THERAPIST_TEMPERATURE`
- `LLM_THERAPIST_MAX_TOKENS`

### Evaluator agent

- `LLM_EVALUATOR_MODEL`
- `LLM_EVALUATOR_TEMPERATURE`
- `LLM_EVALUATOR_MAX_TOKENS`

### Intake agent

- `INTAKE_ENABLED`
- `INTAKE_MIN_USER_TURNS`
- `INTAKE_REQUIRED_FIELDS`
- `INTAKE_CONTEXT_WINDOW_MULTIPLIER`
- `INTAKE_MAX_USER_TURNS_MULTIPLIER`
- `LLM_INTAKE_MODEL`
- `LLM_INTAKE_TEMPERATURE`
- `LLM_INTAKE_MAX_TOKENS`
- `LLM_INTAKE_TOP_P`
- `LLM_INTAKE_FREQUENCY_PENALTY`
- `LLM_INTAKE_PRESENCE_PENALTY`

## Границы ответственности по компонентам

### Telegram слой

Отвечает за:

- прием команд и сообщений;
- wizard-прескрининг;
- отображение сообщений пользователю.

Не отвечает за:

- терапевтическую логику;
- выбор стратегии ответа;
- хранение reasoning.

### Service слой

Отвечает за:

- маршрутизацию;
- сбор state;
- сохранение данных;
- переключение фаз процесса.

Не отвечает за:

- содержимое терапевтического текста;
- определение эмоций;
- выбор психотерапевтической стратегии.

### Agent слой

Отвечает за:

- генерацию терапевтических и intake-ответов;
- аналитические оценки;
- терапевтическую decision-логику.

Не отвечает за:

- Telegram UX;
- жизненный цикл HTTP/бота;
- ORM/транзакции как таковые.

### Repository/DB слой

Отвечает за:

- долговременное хранение;
- восстановление контекста;
- аудит и наблюдаемость.

## Важные архитектурные свойства

### 1. Stateless orchestration

Это главное свойство текущей реализации. Почти все восстанавливается из БД на каждый ход.

### 2. Разделение генерации и оценки

Финальный текст делает `TherapistAgent`, а аналитические подрешения делает `TherapistEvaluator`.

### 3. Разделение process state и clinical state

- `intake_states` хранит прогресс процесса;
- `clinical_profiles` хранит клиническое содержимое.

Это правильное разделение: процесс и доменные данные не смешиваются.

### 4. Персонализация встроена в prompt layer

Настройки "психолога" не зашиты в код поведения, а подмешиваются в prompts и greeting generation.

### 5. Auditability

Система сохраняет не только итоговый ответ, но и reasoning-след:

- decision logs;
- agent logs;
- Langfuse traces.

## Краткая таблица по агентам


| Компонент            | Тип                        | Отвечает за                                                  | Когда вызывается                                           |
| -------------------- | -------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| `DialogueService`    | Оркестратор                | Маршрутизация, state, сессии, сохранение                     | `/start`, каждое сообщение, summary/anket/reset            |
| `IntakeAgent`        | Пользовательский LLM-агент | Сбор и обновление клинической карточки                       | Во всех ходах фазы `intake`                                |
| `TherapistAgent`     | Пользовательский LLM-агент | Основной терапевтический ответ                               | Старт `therapy` и каждый ход в `therapy`                   |
| `TherapistEvaluator` | Внутренний LLM-агент       | Эмоции, стратегия, память, стадия, завершение, выбор терапии | Внутри `TherapistAgent`                                    |
| Prescreening wizard  | Не LLM                     | Настройка персоны и профиля                                  | До первой полноценной сессии или при редактировании анкеты |


## Как это можно объяснять внешне

Если нужно описать систему коротко для команды или заказчика, можно использовать такую формулировку:

> В Opora агент-психолог устроен как оркестрируемая multi-stage система. Сначала пользователь настраивает персону психолога и свой профиль, затем intake-агент собирает первичную клиническую карточку, после чего основной терапевтический агент ведет диалог. При этом отдельный evaluator-агент на каждом ходе скрыто определяет эмоции, стратегию ответа, необходимость памяти и стадию терапии. Все состояние, сообщения, карточка пациента и reasoning-логи хранятся в PostgreSQL, а все LLM-вызовы дополнительно логируются для аудита и наблюдаемости.

## Итог

Архитектурно система "психолога" в `Opora` состоит не из одного промпта, а из нескольких согласованных уровней:

- интерфейсный вход через Telegram;
- prescreening как конфигуратор персоны;
- intake как структурированный клинический сбор;
- therapy как основной пользовательский агент;
- evaluator как внутренний decision engine;
- PostgreSQL как источник истины для состояния;
- logs и Langfuse как слой наблюдаемости.

Именно такое разделение позволяет одновременно:

- персонализировать психолога;
- сохранять терапевтическую логику;
- объяснять решения агента постфактум;
- безопасно восстанавливать состояние между сообщениями.

