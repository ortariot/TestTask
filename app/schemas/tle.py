from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TLEData(BaseModel):
    """Две строки TLE в формате NORAD + необязательное название."""

    line1: str = Field(
        ...,
        min_length=68,
        max_length=68,
        description="Первая строка TLE",
    )
    line2: str = Field(
        ...,
        min_length=68,
        max_length=68,
        description="Вторая строка TLE",
    )
    name: str | None = Field(
        default=None,
        description="Название космического аппарата (опционально)",
    )


class CalculateRequest(BaseModel):
    """Базовые параметры расчёта: TLE, интервал, шаг сетки."""

    tle: TLEData = Field(..., description="TLE спутника")
    start: datetime = Field(..., description="Начало интервала (UTC)")
    end: datetime = Field(..., description="Конец интервала (UTC, не вкл.)")
    step_seconds: int = Field(
        ...,
        ge=1,
        le=60,
        description="Шаг сетки в секундах",
    )

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("start")
        if start is not None and v <= start:
            raise ValueError("end должен быть строго больше start")
        return v
