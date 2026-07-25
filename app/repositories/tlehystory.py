from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

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
        return result.scalar_of_one_or_none()
