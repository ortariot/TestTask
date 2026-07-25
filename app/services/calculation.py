from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from repositories import SpacecraftRepository, TLEHistoryRepository


class OrbitCalculationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        # Инициализируем репозитории внутри сервиса
        self.spacecraft_repo = SpacecraftRepository(session)
        self.tle_repo = TLEHistoryRepository(session)

    async def calculate_satellite_position(
        self, norad_id: int, target_time: datetime
    ):
        # 1. Проверяем, существует ли спутник вообще
        satellite = await self.spacecraft_repo.get_by_id(norad_id)
        if not satellite:
            raise ValueError(f"Satellite {norad_id} not found in database.")

        # 2. Ищем правильный исторический TLE
        tle = await self.tle_repo.get_closest_tle(norad_id, target_time)
        if not tle:
            raise ValueError(f"No TLE array found for date {target_time}")

        # вызов вашей библиотеки SGP4
        return (
            f"Calculated position for {satellite.cospar_id}"
            " using TLE from {tle.epoch_timestamp}"
        )
