from datetime import datetime

from pydantic import BaseModel


class CoordPoint(BaseModel):
    """A single coordinate point."""

    timestamp: datetime
    latitude: float
    longitude: float
    altitude: float


class CalculateResponse(BaseModel):
    points: list[CoordPoint]
    total: int


class CalculateResponsePagination(BaseModel):
    points: list[CoordPoint]
    page: int
    size: int
    total: int
