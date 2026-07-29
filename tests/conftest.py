from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pytest
from api.v1.calculator import router as calc_router
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from schemas.calcreq import CalculationRequest
from services.calculation import (
    OrbitCalculationService,
    get_orbit_calculations_service,
)

VALID_TLE_LINE1 = (
    "1 05398U 71067E   26209.18109351  .00000744  00000+0  23505-3 0  9995"
)
VALID_TLE_LINE2 = (
    "2 05398  87.6249 327.4279 0062195  96.8316 263.9965 14.37917437879777"
)

DEFAULT_START = "2026-07-28T04:00:00Z"
DEFAULT_END = "2026-07-28T05:00:00Z"
DEFAULT_STEP = 10


def build_payload(
    *,
    line1: str = VALID_TLE_LINE1,
    line2: str = VALID_TLE_LINE2,
    name: str | None = "ISS (ZARYA)",
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    step_seconds: int = DEFAULT_STEP,
    content_type: str = "tle",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:

    payload: dict[str, Any] = {
        "content": {
            "content": content_type,
            "line1": line1,
            "line2": line2,
            "name": name,
        },
        "start": start,
        "end": end,
        "step_seconds": step_seconds,
    }

    if extra:
        payload.update(extra)

    return payload


class FakeOrbitCalculationService:
    def __init__(self) -> None:
        self.calls: list[CalculationRequest] = []

    async def calculate_satellite_position(
        self, parameters: CalculationRequest
    ) -> dict[str, Any]:
        self.calls.append(parameters)

        start_ts = int(parameters.start.timestamp())
        end_ts = int(parameters.end.timestamp())
        step = parameters.step_seconds

        timestamps = np.arange(start_ts, end_ts + 1, step, dtype=np.int64)

        dt_objects = timestamps.astype("datetime64[s]")

        points = [
            {
                "timestamp": str(ts),
                "latitude": 0.0,
                "longitude": 0.0,
                "altitude": 0.0,
            }
            for ts in dt_objects
        ]

        return {"points": points, "total": len(points)}


@pytest.fixture
def fake_service() -> FakeOrbitCalculationService:
    return FakeOrbitCalculationService()


@pytest.fixture
def fake_service_factory(
    fake_service: FakeOrbitCalculationService,
):
    def _override() -> OrbitCalculationService:

        return fake_service  # type: ignore[return-value]

    return _override


@pytest.fixture
def app(
    fake_service_factory,
) -> FastAPI:
    application = FastAPI()
    application.include_router(calc_router)

    application.dependency_overrides[get_orbit_calculations_service] = (
        fake_service_factory
    )

    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


def to_utc(dt: datetime) -> datetime:

    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)

    return dt.astimezone(UTC)
