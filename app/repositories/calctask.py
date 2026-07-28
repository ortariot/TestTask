from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import Depends
from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from models import TaskStatus
from models.tlemeta import CalculationTask
from repositories import CRUDRepository


class CalculationTaskRepository(CRUDRepository[CalculationTask]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CalculationTask)

    async def increment_chunks_done(
        self, task_id: int
    ) -> tuple[bool, int, int]:

        stmt = (
            update(CalculationTask)
            .where(
                CalculationTask.id == task_id,
                CalculationTask.status == TaskStatus.PROCESSING,
                CalculationTask.chunks_done < CalculationTask.chunks_total,
            )
            .values(
                chunks_done=CalculationTask.chunks_done + 1,
            )
            .returning(
                CalculationTask.chunks_done,
                CalculationTask.chunks_total,
            )
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row:
            return True, row.chunks_done, row.chunks_total
        return False, 0, 0

    async def finish_task(self, task_id: int) -> bool:

        stmt = (
            update(CalculationTask)
            .where(
                CalculationTask.id == task_id,
                CalculationTask.status == TaskStatus.PROCESSING,
                CalculationTask.chunks_done == CalculationTask.chunks_total,
            )
            .values(
                status=TaskStatus.SUCCESS,
                finished_at=datetime.now(UTC),
            )
        )
        result = cast("CursorResult", await self._session.execute(stmt))
        return result.rowcount > 0

    async def fail_timeout_tasks(self, timeout_minutes: int = 30) -> int:

        stmt = (
            update(CalculationTask)
            .where(
                CalculationTask.status == TaskStatus.PROCESSING,
                CalculationTask.started_at
                < datetime.now(UTC) - timedelta(seconds=timeout_minutes),
                CalculationTask.chunks_done < CalculationTask.chunks_total,
            )
            .values(
                status=TaskStatus.FAILED,
                finished_at=datetime.now(UTC),
            )
        )
        result = cast("CursorResult", await self._session.execute(stmt))
        return result.rowcount


def get_calc_task_repo(
    session: AsyncSession = Depends(get_db_session),
) -> CalculationTaskRepository:
    return CalculationTaskRepository(session)
