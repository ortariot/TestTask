from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        return result.scalar_of_one_or_none()
