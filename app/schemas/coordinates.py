from datetime import datetime

from pydantic import BaseModel


class CoordPoint(BaseModel):
    """Одна точка координат."""

    timestamp: datetime
    latitude: float
    longitude: float
    altitude_km: float


class CalculateResponse(BaseModel):
    """Ответ - список координат"""

    points: list[CoordPoint]
    total: int
