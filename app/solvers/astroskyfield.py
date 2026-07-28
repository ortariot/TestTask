from datetime import UTC, datetime
from typing import Any

import numpy as np
from skyfield.api import EarthSatellite, load
from skyfield.toposlib import wgs84

from schemas.tle import CalculateRequest, TLEData

from .base import AstroCore


class AstrodSkyfield(AstroCore):
    """
    Вычислительное ядро аэрокосмических расчетов на базе Skyfield.
    """

    _ts = load.timescale()

    @classmethod
    def compute_coordinate(
        cls,
        calc_data: CalculateRequest = None,
        tle: TLEData = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        step_seconds: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Векторизованный вычислительный движок на NumPy + Skyfield
        """

        if calc_data:
            raw_line1 = calc_data.tle.line1
            raw_line2 = calc_data.tle.line2
            start_time = calc_data.start
            end_time = calc_data.end
            step_seconds = calc_data.step_seconds
        else:
            raw_line1 = tle.line1
            raw_line2 = tle.line2

        satellite = EarthSatellite(
            raw_line1, raw_line2, name="SAT", ts=cls._ts
        )

        start_ts = int(start_time.astimezone(UTC).timestamp())
        end_ts = int(end_time.astimezone(UTC).timestamp())

        timestamps = np.arange(
            start_ts, end_ts + 1, step_seconds, dtype=np.int64
        )

        if len(timestamps) == 0:
            raise ValueError(
                "Интервал расчета пуст или шаг превышает длительность."
            )

        dt_objects = timestamps.astype("datetime64[s]")

        years = dt_objects.astype("M8[Y]").astype(int) + 1970
        months = dt_objects.astype("M8[M]").astype(int) % 12 + 1
        days = (
            dt_objects.astype("M8[D]") - dt_objects.astype("M8[M]")
        ).astype(int) + 1
        hours = dt_objects.astype("M8[h]").astype(int) % 24
        minutes = dt_objects.astype("M8[m]").astype(int) % 60
        seconds = dt_objects.astype("M8[s]").astype(int) % 60

        skyfield_times = cls._ts.utc(
            years, months, days, hours, minutes, seconds
        )

        geocentric_positions = satellite.at(skyfield_times)

        subpoints = wgs84.subpoint(geocentric_positions)

        latitudes = subpoints.latitude.degrees
        longitudes = subpoints.longitude.degrees
        altitude = subpoints.elevation.km

        time_strings = dt_objects.astype(str)

        trajectory_output = [
            {
                "timestamp": f"{time_strings[i]}Z",
                "latitude": float(latitudes[i]),
                "longitude": float(longitudes[i]),
                "altitude": float(altitude[i]),
            }
            for i in range(len(timestamps))
        ]

        return trajectory_output


def get_solver() -> AstrodSkyfield:
    return AstrodSkyfield()
