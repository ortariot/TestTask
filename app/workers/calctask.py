import asyncio
import math
from datetime import UTC, datetime, timedelta

import structlog

from core.clickhouse import ch_container
from core.settings import settings
from core.taskbroker import broker
from database import db_manager
from models import TaskStatus
from repositories import CalculationTaskRepository
from schemas.calcreq import CalculationRequest
from schemas.orbits import OrbitData
from schemas.tle import TLEData
from solvers.astrospg4 import AstroSPG4

logger = structlog.get_logger()


def current_task_name() -> str:
    task = asyncio.current_task()
    return task.get_name() if task else "unknown"


@broker.task(task_name="process_chunk")
async def process_chunk(  # noqa: PLR0913, PLR0917
    task_id: int,
    chunk_index: int,
    start: datetime,
    end: datetime,
    step_seconds: int,
    content: TLEData | OrbitData,
) -> None:

    task_name = current_task_name()
    logger.info(
        "[%s] MONITORING: Run process_chunk task_id: %s chunk index: %s",
        task_name,
        task_id,
        chunk_index,
    )

    chunk = CalculationRequest(
        content=content, start=start, end=end, step_seconds=step_seconds
    )

    solver = AstroSPG4()
    coords = await asyncio.to_thread(solver.compute_coordinate, chunk)

    bulk_data = [
        [
            task_id,
            chunk_index,
            str(coord["timestamp"]),
            float(coord["latitude"]),
            float(coord["longitude"]),
            float(coord["altitude"]),
        ]
        for coord in coords
    ]
    if bulk_data:
        await ch_container.insert_bulk(bulk_data)

    async with db_manager.session() as session:
        task_repo = CalculationTaskRepository(session)

        updated, done, total = await task_repo.increment_chunks_done(task_id)
        if updated and done == total:
            logger.info(
                "[%s] MONITORING: Task with task_id: %s finished",
                task_name,
                task_id,
            )

            await task_repo.finish_task(task_id)

        await session.commit()

    logger.info(
        "[%s] MONITORING: Finish process_chunk task_id: %s chunk index: %s",
        task_name,
        task_id,
        chunk_index,
    )


@broker.task(task_name="run_master_calculation")
async def run_master_calculation(
    task_id: int, calc_data: CalculationRequest
) -> None:

    if isinstance(calc_data, dict):
        calc_data = CalculationRequest.model_validate(calc_data)

    task_name = current_task_name()
    CHUNK_SIZE = settings.fast_mode_limit

    total_seconds = (calc_data.end - calc_data.start).total_seconds()
    total_points = math.ceil(total_seconds / calc_data.step_seconds)
    chunks_count = math.ceil(total_points / CHUNK_SIZE)

    async with db_manager.session() as session:
        task_repo = CalculationTaskRepository(session)
        await task_repo.update(
            task_id,
            chunks_total=chunks_count,
            status=TaskStatus.PROCESSING,
            started_at=datetime.now(UTC),
        )
        await session.commit()

    logger.info(
        "[%s] MONITORING: Task with task_id: %s is processing",
        task_name,
        task_id,
    )

    for idx in range(chunks_count):
        chunk_start_sec = idx * CHUNK_SIZE * calc_data.step_seconds
        chunk_end_sec = min(
            (idx + 1) * CHUNK_SIZE * calc_data.step_seconds, total_seconds
        )
        chunk_start = calc_data.start + timedelta(seconds=chunk_start_sec)
        chunk_end = calc_data.start + timedelta(seconds=chunk_end_sec)
        await process_chunk.kiq(
            task_id=task_id,
            chunk_index=idx,
            start=chunk_start,
            end=chunk_end,
            step_seconds=calc_data.step_seconds,
            content=calc_data.content,
        )
