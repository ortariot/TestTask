from datetime import datetime

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .orbits import OrbitData
from .tle import TLEData


class CalculationRequest(BaseModel):
    content: TLEData | OrbitData = Field(..., discriminator="content")

    start: datetime
    end: datetime
    step_seconds: int = Field(..., ge=1, le=60)

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, v: datetime, info: ValidationInfo) -> datetime:
        start = info.data.get("start")
        if isinstance(start, datetime) and v <= start:
            raise ValueError("end must be strictly after start")

        return v
