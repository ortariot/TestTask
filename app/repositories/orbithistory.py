from datetime import datetime

from database import get_db_session
from fastapi import Depends
from models.context import OrbitHistory
from schemas.orbits import OrbitData
from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .repositories import CRUDRepository


class OrbitHistoryRepository(CRUDRepository[OrbitHistory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrbitHistory)

    async def get_closest_tle(
        self, norad_id: int, target_date: datetime
    ) -> OrbitHistory | None:

        stmt = (
            select(OrbitHistory)
            .where(
                OrbitHistory.norad_cat_id == norad_id,
                OrbitHistory.epoch <= target_date,
            )
            .order_by(desc(OrbitHistory.epoch))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_if_not_exists(
        self,
        data: OrbitData,
    ) -> None:

        payload = data.model_dump(
            by_alias=False, exclude={"content", "launch_year"}
        )

        if payload.get("epoch") and payload["epoch"].tzinfo is not None:
            payload["epoch"] = payload["epoch"].replace(tzinfo=None)

        stmt = (
            insert(OrbitHistory)
            .values(**payload)
            .on_conflict_do_nothing(
                index_elements=[
                    OrbitHistory.norad_cat_id,
                    OrbitHistory.epoch,
                ]
            )
        )
        await self._session.execute(stmt)


def get_orbit_repo(
    session: AsyncSession = Depends(get_db_session),
) -> OrbitHistoryRepository:
    return OrbitHistoryRepository(session)
