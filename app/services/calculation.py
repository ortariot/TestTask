import asyncio
import math
from datetime import datetime, timedelta
from typing import Any

from core.settings import settings
from database import get_db_session
from fastapi import Depends
from models import CalculationTask
from repositories import (
    CalculationTaskRepository,
    OrbitHistoryRepository,
    SatelliteRepository,
    TLEHistoryRepository,
    get_calc_task_repo,
    get_orbit_repo,
    get_satellite_repo,
    get_tle_repo,
)
from schemas.calcreq import CalculationRequest
from schemas.coordinates import CalculateResponse
from schemas.orbits import OrbitData
from schemas.tle import TLEData
from solvers.astrospg4 import get_solver
from solvers.base import AstroCore
from sqlalchemy.ext.asyncio import AsyncSession
from workers.calctask import run_master_calculation


class OrbitCalculationService:
    FIRST_LAUNCH = 57
    FAST_MODE_LIMIT = settings.fast_mode_limit

    def __init__(
        self,
        session: AsyncSession,
        satellite_repo: SatelliteRepository,
        tle_history_repo: TLEHistoryRepository,
        orbit_hystiry_repo: OrbitHistoryRepository,
        calculation_task_repo: CalculationTaskRepository,
        astro_core: AstroCore,
    ) -> None:
        self.session = session
        self.satellite_repo = satellite_repo
        self.tle_history_repo = tle_history_repo
        self.orbit_hystiry_repo = orbit_hystiry_repo
        self.calculation_task_repo = calculation_task_repo
        self.astro_core = astro_core

    async def _create_sat_meta(
        self,
        norad_id: int,
        classification: str,
        cospar_id: str,
        launch_year: int,
    ) -> None:

        _, created = await self.satellite_repo.get_or_create(
            norad_id=norad_id,
            classification=classification,
            cospar_id=cospar_id,
            launch_year=launch_year,
        )

        if created:
            await self.session.commit()

    async def calculate_satellite_position(
        self, parameters: CalculationRequest
    ) -> CalculateResponse | dict[str, Any]:

        if isinstance(parameters.content, TLEData):
            norad_id, classification, cospar_id, launch_year, era = (
                self._parse_tls(parameters.content)
            )

        if isinstance(parameters.content, OrbitData):
            norad_id = parameters.content.norad_cat_id
            classification = parameters.content.classification_type
            cospar_id = parameters.content.object_id
            era = parameters.content.epoch
            launch_year = parameters.content.launch_year

        await self._create_sat_meta(
            norad_id, classification, cospar_id, launch_year
        )

        if isinstance(parameters.content, TLEData):
            await self.tle_history_repo.add_if_not_exists(
                norad_id=norad_id,
                epoch_timestamp=era,
                raw_line1=parameters.content.line1,
                raw_line2=parameters.content.line2,
            )
            await self.session.commit()

        if isinstance(parameters.content, OrbitData):
            await self.orbit_hystiry_repo.add_if_not_exists(parameters.content)
            await self.session.commit()

        duration_seconds = (parameters.end - parameters.start).total_seconds()
        total_points = math.ceil(duration_seconds / parameters.step_seconds)

        if total_points <= self.FAST_MODE_LIMIT:
            coordinates = await asyncio.to_thread(
                self.astro_core.compute_coordinate, calc_data=parameters
            )

            return {"points": coordinates, "total": total_points}

        else:
            if era and era.tzinfo is not None:
                era = era.replace(tzinfo=None)

            task_kwargs = {
                "start_time": parameters.start,
                "end_time": parameters.end,
                "total_points": total_points,
            }

            if isinstance(parameters.content, TLEData):
                task_kwargs["used_tle_norad_id"] = norad_id
                task_kwargs["used_tle_epoch"] = era
                task_kwargs["used_orbit_norad_id"] = None
                task_kwargs["used_orbit_epoch"] = None
            else:
                task_kwargs["used_tle_norad_id"] = None
                task_kwargs["used_tle_epoch"] = None
                task_kwargs["used_orbit_norad_id"] = norad_id
                task_kwargs["used_orbit_epoch"] = era

            task = CalculationTask(**task_kwargs)

            await self.calculation_task_repo.add(task)
            await self.session.commit()

            await run_master_calculation.kiq(
                task_id=task.id,
                calc_data=parameters,
            )

            return {"task_id": task.id, "status": "pending"}

    def _parse_tls(self, tle: TLEData) -> tuple[int, str, str, int, datetime]:
        """
        return tuple (norad_id, classification, cospar_id, launch_year, era)
        """

        _, norad_id_c, cospar_id_raw, era_raw, *_ = tle.line1.split()

        classification: str = norad_id_c[-1]
        norad_id_str: str = norad_id_c[:-1]
        cospar_id: str = cospar_id_raw
        launch_year = (
            "19" + cospar_id[0:2]
            if int(cospar_id[0:2]) >= self.FIRST_LAUNCH
            else "20" + cospar_id[0:2]
        )

        era = self._parse_tle_era(era_raw)

        return (
            int(norad_id_str),
            classification,
            cospar_id,
            int(launch_year),
            era,
        )

    def _parse_tle_era(self, era_str: str) -> datetime:
        year = 2000 + int(era_str[:2])
        day_of_year = float(era_str[2:])
        start_date = datetime(year - 1, 12, 31)
        return start_date + timedelta(days=day_of_year)


def get_orbit_calculations_service(  # noqa: PLR0913, PLR0917
    session: AsyncSession = Depends(get_db_session),
    satellite_repo: SatelliteRepository = Depends(get_satellite_repo),
    tle_history_repo: TLEHistoryRepository = Depends(get_tle_repo),
    orbit_hystiry_repo: OrbitHistoryRepository = Depends(get_orbit_repo),
    calculation_task_repo: CalculationTaskRepository = Depends(
        get_calc_task_repo
    ),
    slover: AstroCore = Depends(get_solver),
) -> OrbitCalculationService:
    return OrbitCalculationService(
        session=session,
        satellite_repo=satellite_repo,
        tle_history_repo=tle_history_repo,
        orbit_hystiry_repo=orbit_hystiry_repo,
        calculation_task_repo=calculation_task_repo,
        astro_core=slover,
    )
