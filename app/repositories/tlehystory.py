from datetime import datetime

from fastapi import Depends
from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from models.tlemeta import TLEHistory
from repositories import CRUDRepository


class TLEHistoryRepository(CRUDRepository[TLEHistory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TLEHistory)

    async def get_closest_tle(
        self, norad_id: int, target_date: datetime
    ) -> TLEHistory | None:
        """
        запрос находит один TLE, актуальный на заданную историческую дату.
        """
        stmt = (
            select(TLEHistory)
            .where(
                TLEHistory.norad_id == norad_id,
                TLEHistory.epoch_timestamp <= target_date,
            )
            .order_by(desc(TLEHistory.epoch_timestamp))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_if_not_exists(
        self,
        norad_id: int,
        epoch_timestamp: datetime,
        raw_line1: str,
        raw_line2: str,
    ) -> None:
        stmt = (
            insert(TLEHistory)
            .values(
                norad_id=norad_id,
                epoch_timestamp=epoch_timestamp,
                raw_line1=raw_line1,
                raw_line2=raw_line2,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    TLEHistory.norad_id,
                    TLEHistory.epoch_timestamp,
                ]
            )
        )
        await self._session.execute(stmt)


def get_tle_repo(
    session: AsyncSession = Depends(get_db_session),
) -> TLEHistoryRepository:
    return TLEHistoryRepository(session)
