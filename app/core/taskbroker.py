import asyncio

import structlog
import taskiq_fastapi
from fastapi import FastAPI
from taskiq import AsyncBroker, TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from database import db_manager
from repositories import CalculationTaskRepository

from .clickhouse import ch_container, setup_clickhouse
from .settings import settings

logger = structlog.get_logger()

assert settings.redis_dsl is not None, "redis_dsl must be set"
assert settings.db_dsl is not None, "db_dsl must be set"

broker: AsyncBroker = RedisStreamBroker(
    str(settings.redis_dsl.render_as_string(hide_password=False)),
    socket_timeout=None,
).with_result_backend(
    RedisAsyncResultBackend(
        str(settings.redis_dsl.render_as_string(hide_password=False)),
        socket_timeout=None,
    )
)


def _current_task_name() -> str:
    task = asyncio.current_task()
    return task.get_name() if task else "unknown"


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:  # noqa: ARG001
    if settings.db_dsl:
        db_dsl = str(settings.db_dsl.render_as_string(hide_password=False))
    else:
        logger.info("db_dsl not initialized")
        db_dsl = ""
    db_manager.init(db_dsl)
    logger.info("DatabaseSessionManager init success.")
    setup_clickhouse()
    logger.info("ClickHouseContainer init success.")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:  # noqa: ARG001
    if hasattr(db_manager, "close"):
        await db_manager.close()

    ch_container.close()

    logger.info("Databases connection closed")


def init_taskiq(_: FastAPI) -> None:
    taskiq_fastapi.init(broker, "main:app")


@broker.task(schedule=[{"cron": "*/1 * * * *"}])
async def check_timeout_tasks() -> None:
    """
    Clean fail tasks.
    """

    task_name = _current_task_name()
    logger.info(
        "[%s] MONITORING: check failed task ",
        task_name,
    )

    async with db_manager.session() as session:
        task_repo = CalculationTaskRepository(session)
        fail_task = await task_repo.fail_timeout_tasks(settings.taskq_timeout)
        await session.commit()

    if fail_task > 0:
        logger.info(
            "[%s] MONITORING: close %s faild tasks",
            task_name,
            fail_task,
        )
    else:
        logger.info(
            "[%s] MONITORING: No faild tasks found.",
            task_name,
        )


scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)
