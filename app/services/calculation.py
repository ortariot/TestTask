import asyncio
import math

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from repositories import (
    SatelliteRepository,
    TLEHistoryRepository,
    get_satellite_repo,
    get_tle_repo,
)
from schemas.coordinates import CalculateResponse
from schemas.tle import CalculateRequest, TLEData
from solvers.astrospg4 import get_solver
from solvers.base import AstroCore


class OrbitCalculationService:
    FIRST_LAUNCH = 57
    FAST_MODE_MAX_POINTS = 5000

    def __init__(
        self,
        session: AsyncSession,
        satellite_repo: SatelliteRepository,
        tle_history_repo: TLEHistoryRepository,
        astro_core: AstroCore,
    ) -> None:
        self.session = session
        self.satellite_repo = satellite_repo
        self.tle_history_repo = tle_history_repo
        self.astro_core = astro_core

    async def calculate_satellite_position(
        self, parameters: CalculateRequest
    ) -> CalculateResponse | None:

        norad_id, classification, cospar_id, launch_year = self._parse_tls(
            parameters.tle
        )

        satellite, created = await self.satellite_repo.get_or_create(
            norad_id,
            classification=classification,
            cospar_id=cospar_id,
            launch_year=launch_year,
        )

        if created:
            await self.session.commit()

        # TODO добавать обновление исторических данных

        duration_seconds = (parameters.end - parameters.start).total_seconds()
        total_points = math.ceil(duration_seconds / parameters.step_seconds)

        if total_points <= self.FAST_MODE_MAX_POINTS:
            coordinates = await asyncio.to_thread(
                self.astro_core.compute_coordinate, parameters
            )

            return {"points": coordinates, "total": total_points}

        else:
            return None

        return satellite

    def _parse_tls(self, tle: TLEData) -> tuple[int, str, str, str]:
        """
        return tuple (norad_id, classification, cospar_id, launch_year)
        """

        _, norad_id_c, cospar_id, *_ = tle.line1.split()

        classification = norad_id_c[-1]
        norad_id = norad_id_c[:-2]
        launch_year = (
            "19" + cospar_id[0:2]
            if int(cospar_id[0:2]) >= self.FIRST_LAUNCH
            else "20" + cospar_id[0:2]
        )

        return int(norad_id), classification, cospar_id, int(launch_year)


def get_orbit_calculations_service(
    session: AsyncSession = Depends(get_db_session),
    satellite_repo: SatelliteRepository = Depends(get_satellite_repo),
    tle_history_repo: TLEHistoryRepository = Depends(get_tle_repo),
    slover: AstroCore = Depends(get_solver),
) -> OrbitCalculationService:
    return OrbitCalculationService(
        session=session,
        satellite_repo=satellite_repo,
        tle_history_repo=tle_history_repo,
        astro_core=slover,
    )
