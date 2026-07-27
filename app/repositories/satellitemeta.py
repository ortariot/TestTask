from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from models import SatelliteMetadata
from repositories import CRUDRepository


class SatelliteRepository(CRUDRepository[SatelliteMetadata]):
    def __init__(self, session: AsyncSession) -> None:

        super().__init__(session, SatelliteMetadata)

    async def get_by_cospar(self, cospar_id: str) -> SatelliteMetadata | None:
        """метод поиска только для космических аппаратов."""
        stmt = select(SatelliteMetadata).where(
            SatelliteMetadata.cospar_id == cospar_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self, norad_id: int, **create_kwargs
    ) -> tuple[SatelliteMetadata, bool]:

        insert_stmt = (
            insert(SatelliteMetadata)
            .values(norad_id=norad_id, **create_kwargs)
            .on_conflict_do_nothing(
                index_elements=[SatelliteMetadata.norad_id]
            )
            .returning(SatelliteMetadata)
        )

        result = await self._session.execute(insert_stmt)
        inserted_row = result.scalar_one_or_none()

        if inserted_row:
            return inserted_row, True

        existing_stmt = select(SatelliteMetadata).where(
            SatelliteMetadata.norad_id == norad_id
        )
        existing_result = await self._session.execute(existing_stmt)

        return existing_result.scalar_one(), False


def get_satellite_repo(
    session: AsyncSession = Depends(get_db_session),
) -> SatelliteRepository:
    return SatelliteRepository(session)
