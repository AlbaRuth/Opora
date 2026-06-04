# Руководство по развертыванию Opora

## Содержание

1. [Обзор](#обзор)
2. [Миграции базы данных](#миграции-базы-данных)
3. [Rollout (развертывание)](#rollout-развертывание)
4. [Rollback (откат)](#rollback-откат)
5. [Troubleshooting](#troubleshooting)

## Обзор

Opora использует **Alembic** для управления схемой базы данных. Это обеспечивает:
- Версионирование схемы
- Воспроизводимые миграции
- Безопасный rollback при проблемах

Runtime — один процесс Telegram-бота:

| Процесс | Команда | Назначение |
|---------|---------|------------|
| Telegram bot | `.\.venv\Scripts\python.exe bot_runner.py` | Production Telegram polling |

## Миграции базы данных

### Структура миграций

```
alembic/
├── env.py              # Конфигурация окружения
├── script.py.mako      # Шаблон для новых миграций
├── versions/           # Файлы миграций
│   ├── 001_initial_schema.py          # Базовая схема
│   ├── 002_add_prescreening_fields.py # Prescreening
│   └── 003_add_intake_stage.py        # Intake stage
└── README.md           # Документация по Alembic
```

### Команды миграций

```bash
# Показать текущую версию
python scripts/migrate.py current

# Показать историю
python scripts/migrate.py history

# Применить все миграции
python scripts/migrate.py upgrade

# Применить до конкретной ревизии
python scripts/migrate.py upgrade 002

# Откатить на одну версию назад
python scripts/migrate.py downgrade

# Откатить до конкретной версии
python scripts/migrate.py downgrade 001

# Создать новую миграцию
python scripts/migrate.py revision --autogenerate -m "описание"

# Пометить существующую базу (для старых БД)
alembic stamp 001
```

## Rollout (развертывание)

### Development

```bash
# 1. Убедиться, что все изменения моделей имеют миграции
python scripts/check_migrations.py

# 2. Применить миграции
python scripts/migrate.py upgrade

# 3. Создать тестовую БД PostgreSQL (один раз), например: CREATE DATABASE opora_test;
#    Либо задать DATABASE_URL на эту БД; иначе pytest пропустит тесты, требующие БД.

# 4. Запустить тесты (рекомендуется из .venv; Alembic upgrade вызывается при старте pytest)
.\.venv\Scripts\python.exe -m pytest

# 5. Запустить бота
python bot_runner.py
```

### Staging

```bash
# 1. Подготовка
export DATABASE_URL="postgresql+asyncpg://..."

# 2. Создать резервную копию
pg_dump $DATABASE_URL > backup_staging_$(date +%Y%m%d_%H%M%S).sql

# 3. Проверить статус миграций
python scripts/migrate.py current
python scripts/migrate.py history

# 4. Применить миграции
python scripts/migrate.py upgrade

# 5. Проверить результат
python scripts/migrate.py current

# 6. Smoke tests
# - Проверить логи бота после /start

# 7. Запустить бота (если не в Docker)
python bot_runner.py
```

### Production

**⚠️ ВАЖНО: Всегда делайте backup перед миграциями в production!**

```bash
# 1. Создать резервную копию
echo "Creating backup..."
pg_dump $DATABASE_URL > backup_prod_$(date +%Y%m%d_%H%M%S).sql
echo "Backup complete"

# 2. Режим maintenance (если применимо)
# - Отключить бота
# - Установить maintenance mode

# 3. Проверить миграции
python scripts/check_migrations.py
if [ $? -ne 0 ]; then
    echo "Migration checks failed! Aborting."
    exit 1
fi

# 4. Сухой прогон (dry run)
alembic upgrade head --sql > migration_preview.sql
echo "Review migration_preview.sql before proceeding!"

# 5. Применить миграции
python scripts/migrate.py upgrade

# 6. Проверить результат
python scripts/migrate.py current

# 7. Smoke tests
# - Проверить критические функции
# - Проверить логи

# 8. Запустить бота (если не в Docker)
python bot_runner.py
```

### Docker Compose Deployment

```bash
# 1. Запустить инфраструктуру
docker-compose up -d postgres

# 2. Дождаться готовности PostgreSQL
docker-compose exec postgres pg_isready -U opora

# 3. Применить миграции (вне контейнера или внутри)
docker-compose run --rm bot alembic upgrade head

# 4. Запустить бота
docker-compose up -d bot

# Или, если бот настроен с command миграции:
docker-compose up -d
```

## Rollback (откат)

### Определение причины

Перед откатом определите:
1. **Проблема в коде** → Откат кода + откат миграций
2. **Проблема в миграции** → Откат только миграций
3. **Проблема с данными** → Восстановление из backup

### Откат миграций (при ошибке)

```bash
# 1. Остановить бота
pkill -f bot_runner.py

# 2. Проверить текущую версию
python scripts/migrate.py current

# 3. Откатить на предыдущую версию
python scripts/migrate.py downgrade

# 4. Проверить откат
python scripts/migrate.py current

# 5. Запустить бота с предыдущей версией кода
# (git checkout <previous_commit>)
python bot_runner.py
```

### Восстановление из backup

```bash
# 1. Остановить все сервисы
docker-compose down

# 2. Удалить текущие данные (осторожно!)
docker volume rm opora_opora_postgres_data

# 3. Запустить PostgreSQL
docker-compose up -d postgres

# 4. Дождаться готовности
sleep 10

# 5. Восстановить из backup
pg_restore -h localhost -U opora -d opora backup_prod_YYYYMMDD_HHMMSS.sql

# 6. Пометить миграцию
alembic stamp 001  # или актуальная версия на момент backup

# 7. Запустить бота
python bot_runner.py
```

### Emergency Rollback Script

```bash
#!/bin/bash
# emergency_rollback.sh

set -e

# Configuration
BACKUP_FILE="$1"
DB_URL="${DATABASE_URL:-postgresql+asyncpg://opora:opora@localhost:5432/opora}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

echo "=== EMERGENCY ROLLBACK ==="
echo "Backup file: $BACKUP_FILE"
echo "Database: $DB_URL"
echo ""

# Confirm
read -p "Are you sure? This will DESTROY current data! [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Stop bot
echo "Stopping bot..."
pkill -f bot_runner.py || true

# Restore database
echo "Restoring database..."
pg_restore -d "$DB_URL" "$BACKUP_FILE"

# Reset migrations
echo "Resetting migration state..."
alembic stamp 001

# Start bot
echo "Starting bot..."
python bot_runner.py &

echo "Rollback complete!"
```

## Troubleshooting

### Множественные heads

```bash
# Проблема: alembic heads показывает больше одной head

# Решение: merge heads
alembic merge -m "merge heads" <revision1> <revision2>

# Затем upgrade
alembic upgrade head
```

### Несоответствие моделей и базы

```bash
# Проблема: модели изменены, но миграции не созданы

# Проверить
python scripts/check_migrations.py

# Создать миграцию
python scripts/migrate.py revision --autogenerate -m "fix missing migrations"

# Применить
python scripts/migrate.py upgrade
```

### Миграция падает с ошибкой

```bash
# 1. Проверить логи
alembic upgrade head --sql  # Посмотреть SQL без выполнения

# 2. Проверить состояние базы
python scripts/migrate.py current

# 3. Попробовать частично применить
alembic upgrade +1  # Только следующая миграция

# 4. При необходимости - откат
alembic downgrade -1
```

### Старая база без Alembic

```bash
# Проблема: база создана до Alembic

# Решение: stamp текущее состояние
alembic stamp 001  # baseline

# Затем применить остальные миграции
alembic upgrade head
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Database Migration Check
  run: |
    python scripts/check_migrations.py
    
- name: Run Migrations
  run: |
    alembic upgrade head
    
- name: Verify Database
  run: |
    alembic current
```

### Pre-commit hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: check-migrations
        name: Check Alembic migrations
        entry: python scripts/check_migrations.py
        language: system
        pass_filenames: false
```

## Контакты

При проблемах с миграциями:
1. Проверить логи: `logs/app.log`
2. Проверить статус: `alembic current`
3. Связаться с командой разработки

## Справочник команд

| Команда | Описание |
|---------|----------|
| `alembic current` | Текущая версия базы |
| `alembic history` | История миграций |
| `alembic heads` | Активные heads |
| `alembic upgrade head` | Применить все миграции |
| `alembic downgrade -1` | Откатить одну миграцию |
| `alembic stamp <revision>` | Пометить базу без миграции |
| `alembic revision --autogenerate` | Создать миграцию из моделей |
| `python scripts/migrate.py upgrade` | Python wrapper для upgrade |
| `python scripts/check_migrations.py` | Проверить состояние миграций |
