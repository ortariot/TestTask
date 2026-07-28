from datetime import datetime
from typing import Any

import numpy as np
from astropy import units
from astropy.coordinates import ITRS, TEME, CartesianRepresentation
from astropy.time import Time
from schemas.calcreq import CalculationRequest
from schemas.tle import TLEData
from sgp4.api import WGS72, Satrec, jday
from sgp4.omm import initialize

from .base import AstroCore


class AstroSPG4(AstroCore):
    """math core SPG4"""

    @staticmethod
    def compute_coordinate(
        calc_data: CalculationRequest,
    ) -> list[dict[str, Any]]:

        if isinstance(calc_data.content, TLEData):
            raw_line1 = calc_data.content.line1
            raw_line2 = calc_data.content.line2
            satellite = Satrec.twoline2rv(raw_line1, raw_line2)
        else:
            satellite = Satrec()
            omm_dict = calc_data.content.model_dump(
                by_alias=True, exclude={"content", "launch_year"}
            )

            if isinstance(calc_data.content.epoch, datetime):
                omm_dict["EPOCH"] = calc_data.content.epoch.strftime(
                    "%Y-%m-%dT%H:%M:%S.%f"
                )

            initialize(satellite, omm_dict, WGS72)

        start_time = calc_data.start
        end_time = calc_data.end
        step_seconds = calc_data.step_seconds

        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())

        timestamps = np.arange(
            start_ts, end_ts + 1, step_seconds, dtype=np.int64
        )

        if len(timestamps) == 0:
            raise ValueError("not valid time range")

        dt_objects = timestamps.astype("datetime64[s]")
        years = dt_objects.astype("M8[Y]").astype(int) + 1970
        months = dt_objects.astype("M8[M]").astype(int) % 12 + 1
        days = (
            dt_objects.astype("M8[D]") - dt_objects.astype("M8[M]")
        ).astype(int) + 1
        hours = dt_objects.astype("M8[h]").astype(int) % 24
        minutes = dt_objects.astype("M8[m]").astype(int) % 60
        seconds = dt_objects.astype("M8[s]").astype(int) % 60

        jd, fr = jday(years, months, days, hours, minutes, seconds)

        error_codes, positions, _ = satellite.sgp4_array(jd, fr)

        astropy_times = Time(timestamps, format="unix")

        teme_coords = TEME(
            CartesianRepresentation(positions.T * 1000 * units.m),
            obstime=astropy_times,
        )
        itrs_coords = teme_coords.transform_to(ITRS(obstime=astropy_times))
        ellipsoid_coords = itrs_coords.earth_location

        latitudes = ellipsoid_coords.lat.deg
        longitudes = ellipsoid_coords.lon.deg
        heights = ellipsoid_coords.height.to(units.km).value
        time_strings = astropy_times.isot

        trajectory_output = []

        for i in range(len(timestamps)):
            if error_codes[i] != 0:
                continue

            trajectory_output.append(
                {
                    "timestamp": time_strings[i],
                    "latitude": float(latitudes[i]),
                    "longitude": float(longitudes[i]),
                    "altitude": float(heights[i]),
                }
            )

        return trajectory_output


def get_solver() -> AstroSPG4:
    return AstroSPG4()
