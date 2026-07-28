# SAT Coordinates Service

<p align="center"><strong>Микросервис расчёта координат космических аппаратов по данным TLE</strong></p>

Высокопроизводительный бэкенд-сервис для расчёта координат космических аппаратов (КА) на основе орбитальных данных формата **TLE** (Two-Line Element). Сервис рассчитывает траекторию спутника на заданном временном интервале с шагом дискретизации от 1 до 60 секунд и возвращает координаты в системе отсчёта **WGS84** (широта, долгота — градусы, высота — км).

---

## Содержание

- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Стек технологий](#стек-технологий)
- [Структура проекта](#структура-проекта)
- [Быстрый старт (Docker Compose)](#быстрый-старт-docker-compose)
- [Конфигурация](#конфигурация)
- [API](#api)
  - [Расчёт координат](#расчёт-координат)
  - [Получение результата (пагинация)](#получение-результата-пагинация)
  - [Скачивание результата (CSV-стрим)](#скачивание-результата-csv-стрим)
  - [Health-check](#health-check)
- [Вычислительное ядро](#вычислительное-ядро)
- [Модели данных](#модели-данных)
- [Качество кода](#качество-кода)

---

## Возможности

- **Расчёт по TLE** — приём TLE, временного интервала и шага сетки (1–60 с).
- **Векторизованные вычисления** — расчёт всего интервала за один вызов `sgp4_array`/Skyfield.
- **Гибридный режим**:
  - **Fast** — до `FAST_MODE_LIMIT` точек: расчёт выполняется синхронно в пуле потоков и возвращается сразу.
  - **Slow** — сверх лимита: создаётся задача, расчёт дробится на чанки и выполняется воркерами через очередь (TaskIQ + Redis).
- **WGS84** — широта/долгота в градусах, высота в км.
- **Хранилище метаданных** — PostgreSQL: реестр КА (NORAD ID, COSPAR ID, классификация, год запуска) и история TLE.
- **Хранилище временных рядов** — ClickHouse: миллионы точек координат с партицированием по месяцам.
- **Постраничная выборка** и **CSV-стриминг** больших результатов.
- **Идемпотентность** — повторная загрузка того же TLE не создаёт дубликатов (`ON CONFLICT DO NOTHING`).
- **Отказоустойчивость задач** — scheduled-джоба переводит «зависшие» задачи в статус `failed` по таймауту.
- **Наблюдаемость** — structlog-логирование каждого запроса, `/health` endpoint.
- **Строгая типизация** — MyPy strict + SQLAlchemy mypy plugin + Pydantic mypy plugin.

---

## Архитектура

Сервис следует принципам **Clean Architecture** и **Dependency Injection**:

```
┌───────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                  │
│   routers · dependencies · Pydantic schemas               │
└───────────────┬──────────────────────────┬────────────────┘
                │                          │
┌───────────────▼───────────┐  ┌────────────▼───────────────┐
│    Services (use cases)   │  │   Workers (TaskIQ tasks)   │
│  OrbitCalculationService  │  │  run_master_calculation    │
│  CoordinateService        │  │  process_chunk             │
└───────┬──────────┬────────┘  └────────────┬───────────────┘
        │          │                        │
┌───────▼────┐ ┌───▼────────────┐  ┌────────▼────────────────┐
│Repositories│ │  Solvers (DI)  │  │ Infra (PG / CH / Redis) │
│ CRUD + spec│ │  SGP4/Skyfield │  │                         │
└──────┬─────┘ └────────────────┘  └─────────────────────────┘
       │
┌──────▼────────────────────────────────────────────────────┐
│                Models (SQLAlchemy 2.0)                    │
└───────────────────────────────────────────────────────────┘
```

**Ключевые паттерны:**

- **Repository Pattern** — абстрактный `AbstractRepository[ModelType]` → generic `CRUDRepository` → специализированные репозитории (`SatelliteRepository`, `TLEHistoryRepository`, `CalculationTaskRepository`).
- **Strategy Pattern** — `AstroCore` (ABC) с реализациями `AstroSPG4` (SGP4 + Astropy TEME→ITRS) и `AstrodSkyfield` (Skyfield wgs84). Выбор реализации — через DI.
- **Unit of Work** — `DatabaseSessionManager` с контекстным менеджером сессии и автоматическим rollback.
- **Async-to-thread** — блокирующие вычисления (SGP4/Skyfield, ClickHouse) выносятся в пул потоков (`asyncio.to_thread` / `ThreadPoolExecutor`).

---

## Стек технологий

| Слой                      | Технология                                                          |
| ------------------------- | ------------------------------------------------------------------- |
| Язык / фреймворк          | Python 3.12+, FastAPI, Uvicorn                                      |
| Контракты / валидация     | Pydantic v2, pydantic-settings                                      |
| ORM / БД (метаданные)     | SQLAlchemy 2.0+ (async), asyncpg, Alembic                           |
| БД метаданных             | PostgreSQL 17                                                        |
| БД временных рядов        | ClickHouse (MergeTree, partition by month)                          |
| Очередь задач             | TaskIQ + Redis Streams (broker + result backend + scheduler)        |
| Вычислительное ядро       | NumPy, SGP4, Astropy, Skyfield                                      |
| Логирование               | structlog                                                           |
| Качество кода             | Ruff, MyPy (strict), pre-commit                                     |
| Инфраструктура            | Docker (multi-stage), Docker Compose                                |

---

## Структура проекта

```
.
├── docker-compose.yml              # Полное окружение: PG, Redis, ClickHouse, API, worker, scheduler
├── .env                            # Переменные окружения
├── config/
│   └── init-clickhouse.sql         # DDL ClickHouse (авто-инициализация)
└── app/
    ├── main.py                     # Точка входа FastAPI, lifespan, middleware
    ├── Dockerfile                  # Multi-stage build (uv)
    ├── pyproject.toml              # Зависимости, Ruff, MyPy
    ├── database.py                 # DatabaseSessionManager (async SQLAlchemy)
    ├── api/
    │   ├── dependencies/           # DI-провайдеры, валидаторы
    │   └── v1/
    │       ├── tleanalyser.py      # Endpoints расчёта и выдачи координат
    │       └── misk.py             # /health
    ├── core/
    │   ├── settings.py             # pydantic-settings конфигурация
    │   ├── clickhouse.py           # ClickHouse клиент + пул потоков
    │   ├── taskbroker.py           # TaskIQ broker/scheduler, startup/shutdown
    │   ├── exceptions.py           # Доменные исключения
    │   └── logger*.py              # structlog конфигурация + middleware
    ├── models/
    │   └── tlemeta.py              # SatelliteMetadata, TLEHistory, CalculationTask
    ├── schemas/
    │   ├── tle.py                  # CalculateRequest, TLEData
    │   └── coordinates.py          # CoordPoint, CalculateResponse
    ├── repositories/               # CRUDRepository + специализированные репозитории
    ├── services/
    │   ├── calculation.py          # OrbitCalculationService — оркестрация расчёта
    │   └── coordinates.py          # CoordinateService — чтение/стриминг результатов
    ├── solvers/
    │   ├── base.py                 # AstroCore (ABC)
    │   ├── astrospg4.py            # SGP4 + Astropy (TEME → ITRS → WGS84)
    │   └── astroskyfield.py        # Skyfield (wgs84.subpoint)
    ├── workers/
    │   └── calctask.py             # TaskIQ-задачи: master (чанки) + process_chunk
    └── migrations/                 # Alembic-миграции
```

---

## Быстрый старт (Docker Compose)


```bash
# 1. Клонировать репозиторий
git clone https://github.com/ortariot/TestTask.git
cd TestTask

mv .emv_example .env

# 2. Запустить все сервисы
docker compose up -d --build
```

После запуска:

- **API**: `http://localhost:8000`
- **Swagger UI**: `http://localhost:8000/docs`
- **Health**: `http://localhost:8000/health`

Миграции БД применяются **автоматически** при старте контейнера API (`alembic upgrade head`). Схема ClickHouse создаётся из `config/init-clickhouse.sql`.

### Состав сервисов

| Сервис          | Назначение                                              |
| --------------- | ------------------------------------------------------- |
| `sat-postgres`  | Метаданные КА, история TLE, реестр задач                |
| `sat-redis`     | Брокер очереди задач (TaskIQ Streams)                   |
| `sat-clickhouse`| Хранилище временных рядов координат                     |
| `sat-api`       | FastAPI-приложение (REST API)                           |
| `sat-worker`    | TaskIQ-воркеры (фоновый расчёт чанков, 4 воркера)       |
| `sat-scheduler` | TaskIQ-планировщик (контроль зависших задач)            |

---

## Конфигурация

Все параметры задаются через переменные окружения (`.env`):

| Переменная          | По умолчанию     | Описание                                     |
| ------------------- | ---------------- | -------------------------------------------- |
| `POSTGRES_USER`     | `postgres`       | Пользователь PostgreSQL                       |
| `POSTGRES_PASSWORD` | `postgres`       | Пароль PostgreSQL                             |
| `POSTGRES_DB`       | `app_db`         | База данных PostgreSQL                        |
| `DB_HOST`           | `sat-postgres`   | Хост PostgreSQL                               |
| `DB_PORT`           | `5432`           | Порт PostgreSQL                               |
| `REDIS_HOST`        | `sat-redis`      | Хост Redis                                    |
| `REDIS_PORT`        | `6379`           | Порт Redis                                    |
| `REDIS_PASSWORD`    | —                | Пароль Redis                                  |
| `CLICKHOUSE_HOST`   | `sat-clickhouse` | Хост ClickHouse                               |
| `CLICKHOUSE_PORT`   | `8123`           | HTTP-порт ClickHouse                          |
| `CLICKHOUSE_DB`     | `sat`            | База данных ClickHouse                        |
| `FAST_MODE_LIMIT`   | `5000`           | Порог точек для синхронного расчёта           |
| `TASKQ_TIMEOUT`     | `3600`           | Таймаут задачи (сек) перед пометкой `failed`  |

---

## API

### Расчёт координат

`POST /coordinates_calculate`

Принимает TLE, временной интервал и шаг сетки. Если число точек ≤ `FAST_MODE_LIMIT` — возвращает результат сразу. Иначе — создаёт фоновую задачу и отвечает `202` с `task_id`.

#### Пример запроса (на основе реального TLE ISS с Celestrak)

```bash
curl -X POST http://localhost:8000/coordinates_calculate \
  -H "Content-Type: application/json" \
  -d '{
    "tle": {
      "name": "ISS (ZARYA)",
      "line1": "1 25544U 98067A   25209.50255776  .00013227  00000+0  23758-3 0  9993",
      "line2": "2 25544  51.6418 226.9119 0003134 261.6270 264.0460 15.49990995502311"
    },
    "start": "2025-07-28T12:00:00Z",
    "end":   "2025-07-28T13:00:00Z",
    "step_seconds": 10
  }'
```

**Быстрый ответ (≤ 5000 точек):**

```json
{
  "points": [
    {"timestamp": "2025-07-28T12:00:00.000", "latitude": 45.12, "longitude": 12.34, "altitude": 420.5}
  ],
  "total": 360
}
```

**Отложенный ответ (> 5000 точек):**

```json
{
  "task_id": 42,
  "status": "pending"
}
```

---

### Получение результата (пагинация)

`GET /tasks/{task_id}/coordinates?page=1&size=100`

Возвращает координаты постранично. Если задача ещё не завершена — ответ `202` с текущим статусом.

```bash
curl http://localhost:8000/tasks/42/coordinates?page=1&size=100
```

```json
{
  "points": [
    {"timestamp": "...", "latitude": 45.12, "longitude": 12.34, "altitude": 420.5}
  ],
  "page": 1,
  "size": 100,
  "total": 50000
}
```

---

### Скачивание результата (CSV-стрим)

`GET /tasks/{task_id}/coordinates/download?offset_row=0&limit_row=1000000`

Возвращает CSV-поток (до 1 000 000 строк) — удобно для выгрузки больших расчётов без загрузки всего массива в память.

```bash
curl -OJ http://localhost:8000/tasks/42/coordinates/download
```

---

### Health-check

`GET /health`

```json
{ "status": "ok", "version": "0.0.1" }
```


---

## Вычислительное ядро

Реализованы две стратегии расчёта (наследники `AstroCore`), переключаемые через DI:

### 1. AstroSPG4 (основной)

```
TLE → Satrec.twoline2rv → sgp4_array(jd, fr) → TEME (км)
    → Astropy TEME→ITRS → EarthLocation → WGS84 (lat, lon, alt)
```

- Векторизованный расчёт всего интервала за один вызов `sgp4_array`.
- Преобразование координат: **TEME → ITRS** через Astropy (учёт вращения Земли).
- Фильтрация точек с ненулевым кодом ошибки SGP4.

### 2. AstrodSkyfield (альтернативный)

```
TLE → EarthSatellite → satellite.at(times) → wgs84.subpoint → (lat, lon, alt)
```

- Использует встроенную реализацию SGP4 и модели wgs84 из Skyfield.

Оба ядра строят массив `timestamps` через `np.arange`, формируют bulk-запрос к расчётному движку и возвращают список точек без Python-циклов по вычислениям.

---

## Модели данных

### PostgreSQL

**`satellite_metadata`** — реестр космических аппаратов:

| Поло             | Тип         | Описание                                   |
| ---------------- | ----------- | ------------------------------------------ |
| `norad_id` (PK)  | BIGINT      | NORAD ID                                   |
| `cospar_id` (UQ) | CHAR(8)     | COSPAR ID (международный идентификатор)     |
| `classification` | CHAR(1)     | U/C/S                                      |
| `launch_year`    | SMALLINT    | Год запуска (≥ 1957)                       |
| `created_at`     | TIMESTAMP   | —                                          |
| `updated_at`     | TIMESTAMP   | —                                          |

**`tle_history`** — история TLE (RANGE-партиционирование по `epoch_timestamp`):

| Поло                          | Тип       | Описание                          |
| ----------------------------- | --------- | --------------------------------- |
| `norad_id` (PK, FK)           | BIGINT    | Ссылка на `satellite_metadata`    |
| `epoch_timestamp` (PK)        | TIMESTAMP | Эпоха TLE                         |
| `raw_line1` / `raw_line2`     | CHAR(69)  | Строки TLE                        |

**`calculation_tasks`** — реестр задач расчёта:

| Поло             | Тип         | Описание                                  |
| ---------------- | ----------- | ----------------------------------------- |
| `id` (PK)        | BIGINT      | Автоинкремент                              |
| `start_time`     | TIMESTAMPTZ | Начало интервала расчёта                   |
| `end_time`       | TIMESTAMPTZ | Конец интервала расчёта                    |
| `total_points`   | BIGINT      | Кол-во точек                               |
| `status`         | VARCHAR(20) | `pending` / `processing` / `success` / `failed` |
| `task_type`      | VARCHAR(20) | `fast` / `slow` / `precision`              |
| `chunks_total`   | SMALLINT    | Всего чанков                               |
| `chunks_done`    | SMALLINT    | Выполнено чанков                           |
| `used_tle_*`     | —           | FK на TLE (norad_id + epoch)               |
| `started_at`     | TIMESTAMPTZ | —                                          |
| `finished_at`    | TIMESTAMPTZ | —                                          |

### ClickHouse

**`coordinates`** — временной ряд координат (MergeTree):

```sql
CREATE TABLE sat.coordinates (
    task_id      UInt64,
    chunk_index  UInt32,
    timestamp    DateTime64(3),
    latitude     Float64,
    longitude    Float64,
    altitude     Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (task_id, timestamp);
```

---

## Качество кода

- **Ruff** — расширенный набор правил: `E`, `W`, `F`, `I`, `B`, `C4`, `UP`, `ARG`, `PTH`, `S`, `BLE`, `ERA`, `PL`, `RUF`.
- **MyPy strict** с плагинами Pydantic и SQLAlchemy.
- **pre-commit** хуки для автоматической проверки перед коммитом.

```bash
cd app

# Линтинг и форматирование
uv run ruff check .
uv run ruff format .

# Проверка типов
uv run mypy .
```