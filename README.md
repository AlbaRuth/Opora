# Opora — агент психологического консультирования

Рефакторинг архитектуры с сохранением исходной логики агента и переходом на современную инфраструктуру.

## Архитектура

```
OporaNew/
├── core/              # Конфигурация и логирование
├── db/                # Модели БД, репозитории, управление сессиями
├── agents/            # Логика агента (сохранена из оригинала)
│   ├── core/          # TherapistAgent
│   ├── evaluators/    # TherapistEvaluator
│   └── prompts/       # Шаблоны промптов
├── integrations/      # Внешние интеграции
│   ├── openrouter/    # LLM-клиент
│   ├── telegram/      # Интеграция с ботом
│   └── langfuse/      # Наблюдаемость
├── services/          # Слой бизнес-логики
├── scripts/           # Скрипты миграции и утилиты
└── tests/             # Набор тестов
```

## Ключевые принципы

1. **Логика агента сохранена**: вся логика принятия решений из оригинального `Opora/agent/` сохранена без изменений
2. **Современная инфраструктура**: PostgreSQL, структурированное логирование, наблюдаемость через Langfuse
3. **Слоистая архитектура**: четкое разделение между агентами, сервисами и интеграциями
4. **Конфигурация через окружение**: все настройки задаются через `.env`

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

# 4. Применить миграции базы данных
python scripts/migrate.py upgrade

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
python scripts/migrate.py upgrade

# 5. Проверить текущую версию миграций
python scripts/migrate.py current

# 6. Запустить бота
python bot_runner.py
```

### 🛑 Остановка

```bash
# Остановить PostgreSQL
docker-compose down

# Остановить и удалить данные (осторожно!)
docker-compose down -v
```

## Сохранение исходной логики

Следующие файлы содержат сохраненную логику агента:

- `agents/core/therapist_agent.py` — основная оркестрация агента (main.py, строки 39-289)
- `agents/evaluators/therapist_evaluator.py` — вся логика оценки (evaluation.py)
- `agents/prompts/therapist_prompts.py` — промпты генерации ответа
- `agents/prompts/evaluator_prompts.py` — все промпты оценщика

Все промпты, потоки принятия решений и критерии оценки идентичны оригинальной реализации Opora.

## Миграции базы данных (Alembic)

Проект использует **Alembic** для версионирования схемы базы данных.

### Основные команды

```bash
# Показать текущую версию миграции
python scripts/migrate.py current

# Показать историю миграций
python scripts/migrate.py history

# Применить все миграции (для новых баз)
python scripts/migrate.py upgrade

# Откатить на одну версию назад (осторожно!)
python scripts/migrate.py downgrade

# Создать новую миграцию после изменения моделей
python scripts/migrate.py revision --autogenerate -m "описание изменений"
```

### Для существующих баз данных (до Alembic)

Если у вас есть существующая база, созданная до внедрения Alembic:

```bash
# 1. Пометить текущее состояние базы как baseline
alembic stamp 001

# 2. Применить все последующие миграции
python scripts/migrate.py upgrade
```

### Workflow для разработчиков

1. **Изменяете модели** в `db/models/`
2. **Создаете миграцию**: `python scripts/migrate.py revision --autogenerate -m "добавлено поле X"`
3. **Проверяете SQL** в созданном файле `alembic/versions/`
4. **Применяете**: `python scripts/migrate.py upgrade`
5. **Тестируете** и отправляете PR с моделями + миграцией

## Схема базы данных

### Users
- Информация о пользователях Telegram
- Кэш медицинской карты

### Therapy Sessions
- Метаданные и состояние сессии
- Тип терапии и обоснование

### Messages
- История диалога
- Кэш анализа эмоций

### Decision Logs
- Снимки решений агента
- Полные данные решений для аудита

### Agent Logs
- Логи вызовов LLM с промптами/ответами
- Задержка и расход токенов
- Корреляция с Langfuse

## Логирование

Три потока логов:
1. **Service Logs** — инфраструктура, ошибки, события выполнения
2. **Agent Logs** — вызовы LLM, решения, рассуждения
3. **Audit Logs** — логи доступа с редактированием PII

## Переменные окружения

Поддерживаются все переменные из `.env` проекта SupportAssistant:

- `DATABASE_URL` — подключение к PostgreSQL
- `TELEGRAM_BOT_TOKEN` — токен бота
- `OPENROUTER_*` — настройки LLM-провайдера
- `LANGFUSE_*` — настройки наблюдаемости
- `LOG_*` — конфигурация логирования
