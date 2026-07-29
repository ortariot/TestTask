# 🛰️ SAT Coordinates Service

<div align="center">

**Высокопроизводительный микросервис расчёта координат космических аппаратов по данным TLE / OMM**

---

`FastAPI` · `Pydantic v2` · `SQLAlchemy 2.0 async` · `SGP4` · `Skyfield` · `Astropy` · `NumPy` · `ClickHouse` · `TaskIQ`

</div>

---
## Пояснительная записка

Комментарий к решению 


Основным условием за которое зацепился было вот это:
```Сервис должен быстро рассчитать и вернуть координаты КА на заданный интервал времени.```

Что следует считать быстро? tle снимается со спутника несколько раз в сутки и достаточно точный расчет можно совершить в диапазоне 1-2 суток от момента получения tle. Дальнейшие расчёты накапливают погрешности и мало чего общего будут иметь с реальными показателями спутника. То есть приблизительно нужно рассчитывать 200000 точек и делать это быстро.    

Мне удалось сделать расчетки на основе skyfield и sgp4 которые считают 10000 точек примерно за 5 секунд. Это не быстро но эти данные еще нужно передать в ответ. В итоге я ограничил быстрый расчёт 5000 точек на моём железе. И выполняю эти расчёты на лету 

Для того чтобы выполнять обсчет 200000 и более потребовалось создать гибридную архитектуру и использовать очередь сообщений на основе TaskQ + Redis и выполнять расчёты параллельно. Этого решения вполне достаточно для поставленной задачи. В финальной версии проекта я также использовал clickhouse и мне удалось выполнить расчёты 15000000 координат ~ 60 секунд. Это уже избыточно для задачи, и не понятно что с этими координатами сразу потом делать, но считаю производительность более чем достойная. Пришлось добавить в сервис 2 эндпоинт чтобы отдавать эти результаты либо в виде файла либо с пагинацией. 

Также я использовал базу данных postgres для сохранения истории расчётов, метаданных, и контроля за выполнением задач. 

В Принципе была идея, на лету обновлять TLE, забирать их из API или настроить ETL с https://celestrak.org/ и получать более точные результаты, но руки уже не дошли.



## О проекте

Сервис принимает орбитальные данные КА в формате **TLE** (Two-Line Element) или **JSON/OMM** (орбитальные элементы), временной интервал и шаг дискретизации (1–60 с), после чего **быстро** рассчитывает траекторию спутника и возвращает координаты в системе отсчёта **WGS84** (широта, долгота — градусы, высота — км).

Расчёт опирается на векторизованные вычисления (`sgp4_array` + NumPy), поддерживает интервалы как в прошлое, так и в будущее относительно эпохи TLE, и автоматически выбирает режим выполнения — **синхронный** (для небольших интервалов) или **асинхронный через очередь задач** (для больших).


---

## Ключевые возможности

| Возможность | Реализация |
|---|---|
| **Векторизованный расчёт** | Один вызов `sgp4_array` на весь интервал, без Python-циклов по точкам |
| **Стратегия вычислений (Strategy + DI)** | `AstroCore` (ABC) → `AstroSPG4` (SGP4 + Astropy TEME→ITRS) и `AstrodSkyfield` (Skyfield wgs84) |
| **Гибридный режим Fast/Slow** | ≤ `FAST_MODE_LIMIT` точек — ответ сразу; свыше — очередь TaskIQ + чанкинг |
| **Корректная система координат** | TEME → ITRS с учётом вращения Земли (Astropy) → WGS84 (lat/lon/alt) |
| **Строгая валидация TLE** | Длина 69, префиксы, NORAD-checksum, совпадение спутника, sanity-check SGP4 |
| **Хранилище метаданных** | PostgreSQL: реестр КА, история TLE/OMM, реестр задач |
| **Хранилище временных рядов** | ClickHouse (MergeTree, partition by month) + CSV-стриминг до 1 000 000 строк |
| **Clean Architecture + DI** | `api → services → repositories → models`, абстракции и контракты |
| **Строгая типизация** | MyPy strict + плагины Pydantic и SQLAlchemy |
| **Наблюдаемость** | structlog-логирование каждого запроса, `/health` endpoint |
| **Отказоустойчивость задач** | Планировщик переводит «зависшие» задачи в статус `failed` по таймауту |

---

##  Архитектура

```text
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                        │
│            routers · dependencies · Pydantic schemas            │
└───────────────┬────────────────────────────┬────────────────────┘
                │                            │
┌───────────────▼──────────────┐  ┌──────────▼───────────────────┐
│     Services (use cases)     │  │    Workers (TaskIQ tasks)    │
│  OrbitCalculationService     │  │     run_master_calculation   │
│  CoordinateService           │  │       process_chunk          │
└───────┬──────────────┬───────┘  └────────────┬─────────────────┘
        │              │                       │
┌───────▼──────┐ ┌─────▼──────────┐  ┌─────────▼──────────────────┐
│ Repositories │ │  Solvers (DI)  │  │  Infra (PG / CH / Redis)   │
│  CRUD + spec │ │ SGP4 / Skyfield│  │                            │
└──────┬───────┘ └────────────────┘  └────────────────────────────┘
       │
┌──────▼─────────────────────────────────────────────────────────┐
│                  Models (SQLAlchemy 2.0, async)                │
└────────────────────────────────────────────────────────────────┘
```

**Паттерны:**
- **Repository** — generic `CRUDRepository[ModelType]` → специализированные репозитории.
- **Strategy** — переключаемое вычислительное ядро через DI.
- **Unit of Work** — `DatabaseSessionManager` с автоматическим rollback.
- **Async-to-thread** — блокирующие вычисления (SGP4/Skyfield, ClickHouse) выносятся в пул потоков.

---

##  Стек технологий

| Слой | Технология |
|---|---|
| Язык / фреймворк | **Python 3.12+**, FastAPI, Uvicorn |
| Контракты / валидация | Pydantic v2, pydantic-settings |
| ORM / БД (метаданные) | SQLAlchemy 2.0+ (async), asyncpg, Alembic |
| БД метаданных | PostgreSQL 17 |
| БД временных рядов | ClickHouse (MergeTree, partition by month) |
| Очередь задач | TaskIQ + Redis Streams |
| Вычислительное ядро | NumPy, SGP4, Astropy, Skyfield |
| Логирование | structlog |
| Качество кода | Ruff, MyPy (strict), pre-commit |
| Инфраструктура | Docker (multi-stage), Docker Compose |

---

##  Структура проекта

```text
.
├── docker-compose.yml              # Полное окружение одной командой
├── .env _example                   # Шаблон переменных окружения
├── config/
│   └── init-clickhouse.sql         # DDL ClickHouse (авто-инициализация)
├── tests/                          # Тесты API-контракта и срезов времени
│   ├── conftest.py
│   ├── test_coordinates_validation.py
│   └── test_time_slicing.py
└── app/
    ├── main.py                     # Точка входа FastAPI, lifespan, middleware
    ├── Dockerfile                  # Multi-stage build (uv)
    ├── pyproject.toml              # Зависимости, Ruff, MyPy, pytest
    ├── database.py                 # DatabaseSessionManager (async SQLAlchemy)
    ├── api/
    │   ├── dependencies/           # DI-провайдеры, валидаторы
    │   └── v1/
    │       ├── calculator.py       # Endpoints расчёта и выдачи координат
    │       └── misc.py             # /health
    ├── core/
    │   ├── settings.py             # pydantic-settings конфигурация
    │   ├── clickhouse.py           # ClickHouse клиент + пул потоков
    │   ├── taskbroker.py           # TaskIQ broker/scheduler
    │   ├── exceptions.py           # Доменные исключения
    │   └── logger*.py              # structlog конфигурация + middleware
    ├── models/
    │   └── context.py              # SatelliteMetadata, TLEHistory, OrbitHistory, CalculationTask
    ├── schemas/
    │   ├── calcreq.py              # CalculationRequest (union с дискриминатором)
    │   ├── coordinates.py          # CoordPoint, CalculateResponse
    │   ├── tle.py                  # TLEData (строгая валидация TLE)
    │   └── orbits.py               # OrbitData (OMM/JSON)
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

##  Быстрый старт (Docker Compose)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/ortariot/TestTask.git
cd TestTask

# 2. Подготовить файл окружения
cp ".env _example" .env

# 3. Поднять всю инфраструктуру одной командой
docker compose up -d --build
```

После запуска:

| Сервис | URL / назначение |
|---|---|
| **API** | `http://localhost:8000` |
| **Swagger UI** | `http://localhost:8000/docs` |
| **Health-check** | `http://localhost:8000/health` |

Миграции PostgreSQL применяются **автоматически** при старте API (`alembic upgrade head`). Схема ClickHouse создаётся из `config/init-clickhouse.sql`.

### Состав сервисов

| Контейнер | Назначение |
|---|---|
| `sat-postgres` | Метаданные КА, история TLE/OMM, реестр задач |
| `sat-redis` | Брокер очереди задач (TaskIQ Streams) |
| `sat-clickhouse` | Хранилище временных рядов координат |
| `sat-api` | FastAPI-приложение (REST API) |
| `sat-worker` | TaskIQ-воркеры (фоновый расчёт чанков) |
| `sat-scheduler` | TaskIQ-планировщик (контроль зависших задач) |

---

##  Тесты

Проект покрыт тестами на Тесты мокают вычислительное ядро и проверяют валидацию запросов, обработку невалидных TLE, граничные значения шага, монотонность и количество точек.

```bash
cd app

# Запуск всех тестов
uv run pytest -v

# Только валидация контрактов (TLE, шаг, даты)
uv run pytest -v -m validation

# Только проверка срезов времени (кол-во точек, монотонность)
uv run pytest -v -m time_slicing
```

---

## 📡 API

### 1. Расчёт координат

`POST /coordinates_calculate`

Принимает TLE или OMM, временной интервал и шаг сетки. Если число точек ≤ `FAST_MODE_LIMIT` — возвращает результат сразу. Иначе — создаёт фоновую задачу и отвечает `202` с `task_id`.

#### Пример запроса по TLE (ISS с Celestrak)

```bash
curl -X POST http://localhost:8000/coordinates_calculate \
  -H "Content-Type: application/json" \
  -d '{
        "content": {
            "content": "tle",
            "line1": "1 25544U 98067A   24089.70425714  .00014761  00000-0  26402-3 0  9997",
            "line2": "2 25544  51.6416 195.8450 0004245 214.3989 240.2317 15.49509425445831",
            "name": "ISS (ZARYA)"
        },
        "start": "2026-07-28T04:00:00Z",
        "end": "2026-07-28T05:00:00Z",
        "step_seconds": 10
    }'
```

#### Пример запроса по JSON/OMM (Progress-MS33)

```bash
curl -X POST http://localhost:8000/coordinates_calculate \
  -H "Content-Type: application/json" \
  -d '{
        "content": {
            "content": "orbit",
            "OBJECT_NAME": "PROGRESS-MS33",
            "OBJECT_ID": "2026-058A",
            "EPOCH": "2026-07-28T03:39:38.218752Z",
            "MEAN_MOTION": 15.49220842,
            "ECCENTRICITY": 0.0007093,
            "INCLINATION": 51.632,
            "RA_OF_ASC_NODE": 97.3682,
            "ARG_OF_PERICENTER": 345.612,
            "MEAN_ANOMALY": 14.4666,
            "EPHEMERIS_TYPE": 0,
            "CLASSIFICATION_TYPE": "U",
            "NORAD_CAT_ID": 68319,
            "ELEMENT_SET_NO": 999,
            "REV_AT_EPOCH": 57794,
            "BSTAR": 0.00020282,
            "MEAN_MOTION_DOT": 0.00010831,
            "MEAN_MOTION_DDOT": 0
        },
        "start": "2026-07-28T04:00:00Z",
        "end": "2026-07-28T05:00:00Z",
        "step_seconds": 10
    }'
```

**Быстрый ответ (≤ 5000 точек):**

```json
{
  "points": [
    {"timestamp": "2026-07-28T04:00:00.000", "latitude": 45.12, "longitude": 12.34, "altitude": 420.5}
  ],
  "total": 361
}
```

**Отложенный ответ (> 5000 точек):**

```json
{
  "task_id": 42,
  "status": "pending"
}
```

### 2. Получение результата (пагинация)

`GET /tasks/{task_id}/coordinates?page=1&size=100`

```bash
curl "http://localhost:8000/tasks/42/coordinates?page=1&size=100"
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

### 3. Скачивание результата (CSV-стрим)

`GET /tasks/{task_id}/coordinates/download?offset_row=0&limit_row=1000000`

```bash
curl -OJ "http://localhost:8000/tasks/42/coordinates/download"
```

### 4. Health-check

`GET /health`

```json
{ "status": "ok", "version": "0.0.1" }
```

---

##  Вычислительное ядро

Реализованы две стратегии расчёта (наследники `AstroCore`), переключаемые через DI:

### AstroSPG4 (основной)

```text
TLE → Satrec.twoline2rv → sgp4_array(jd, fr) → TEME (км)
    → Astropy TEME→ITRS → EarthLocation → WGS84 (lat, lon, alt)
```

- Векторизованный расчёт всего интервала за один вызов `sgp4_array`.
- Преобразование координат: **TEME → ITRS** через Astropy (учёт вращения Земли).
- Фильтрация точек с ненулевым кодом ошибки SGP4.

### AstrodSkyfield (альтернативный)

```text
TLE → EarthSatellite → satellite.at(times) → wgs84.subpoint → (lat, lon, alt)
```

Оба ядра строят массив `timestamps` через `np.arange`, формируют bulk-запрос к расчётному движку и возвращают точки без Python-циклов по вычислениям.

---

## Модели данных

### PostgreSQL

**`satellite_metadata`** — реестр космических аппаратов:

| Поле | Тип | Описание |
|---|---|---|
| `norad_id` (PK) | BIGINT | NORAD ID |
| `cospar_id` (UQ) | VARCHAR(15) | COSPAR ID (международный идентификатор) |
| `classification` | CHAR(1) | U/C/S |
| `launch_year` | SMALLINT | Год запуска (≥ 1957) |
| `created_at` / `updated_at` | TIMESTAMP | — |

**`tle_history`** — история TLE (композитный PK `norad_id` + `epoch_timestamp`):

| Поле | Тип | Описание |
|---|---|---|
| `norad_id` (PK, FK) | BIGINT | Ссылка на `satellite_metadata` |
| `epoch_timestamp` (PK) | TIMESTAMP | Эпоха TLE |
| `raw_line1` / `raw_line2` | CHAR(69) | Строки TLE |

**`orbit_history`** — история OMM/JSON (композитный PK `norad_cat_id` + `epoch`).

**`calculation_tasks`** — реестр задач расчёта:

| Поле | Тип | Описание |
|---|---|---|
| `id` (PK) | BIGINT | Автоинкремент |
| `start_time` / `end_time` | TIMESTAMPTZ | Интервал расчёта |
| `total_points` | BIGINT | Кол-во точек |
| `status` | VARCHAR(20) | `pending` / `processing` / `success` / `failed` |
| `task_type` | VARCHAR(20) | `fast` / `slow` / `precision` |
| `chunks_total` / `chunks_done` | SMALLINT | Прогресс чанков |
| `used_tle_*` / `used_orbit_*` | — | FK на источник данных (XOR-констрейнт) |
| `started_at` / `finished_at` | TIMESTAMPTZ | — |

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

## Конфигурация

Все параметры задаются через переменные окружения (`.env`):

| Переменная | По умолчанию | Описание |
|---|---|---|
| `POSTGRES_USER` | `postgres` | Пользователь PostgreSQL |
| `POSTGRES_PASSWORD` | `postgres` | Пароль PostgreSQL |
| `POSTGRES_DB` | `app_db` | База данных PostgreSQL |
| `DB_HOST` | `sat-postgres` | Хост PostgreSQL |
| `DB_PORT` | `5432` | Порт PostgreSQL |
| `REDIS_HOST` | `sat-redis` | Хост Redis |
| `REDIS_PORT` | `6379` | Порт Redis |
| `REDIS_PASSWORD` | — | Пароль Redis |
| `CLICKHOUSE_HOST` | `sat-clickhouse` | Хост ClickHouse |
| `CLICKHOUSE_PORT` | `8123` | HTTP-порт ClickHouse |
| `CLICKHOUSE_DB` | `sat` | База данных ClickHouse |
| `FAST_MODE_LIMIT` | `5000` | Порог точек для синхронного расчёта |
| `TASKQ_TIMEOUT` | `3600` | Таймаут задачи (сек) перед пометкой `failed` |

---

## Качество кода

```bash
cd app

# Линтинг и форматирование
uv run ruff check .
uv run ruff format .

# Проверка типов (strict + плагины Pydantic/SQLAlchemy)
uv run mypy .
```

- **Ruff** — расширенный набор правил: `E`, `W`, `F`, `I`, `B`, `C4`, `UP`, `ARG`, `PTH`, `S`, `BLE`, `ERA`, `PL`, `RUF`.
- **MyPy strict** с плагинами Pydantic и SQLAlchemy.
- **pre-commit** хуки для автоматической проверки перед коммитом.