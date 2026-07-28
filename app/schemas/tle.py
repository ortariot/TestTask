from typing import Literal

from pydantic import BaseModel, Field


class TLEData(BaseModel):
    content: Literal["tle"] = "tle"

    line1: str = Field(
        ...,
        min_length=69,
        max_length=69,
        description="first TLE",
        examples=[
            "1 25544U 98067A   24089.70425714  .00014761  00000-0  26402-3 0  9997"
        ],
    )
    line2: str = Field(
        ...,
        min_length=69,
        max_length=69,
        description="second TLE",
        examples=[
            "2 25544  51.6416 195.8450 0004245 214.3989 240.2317 15.49509425445831"
        ],
    )
    name: str | None = Field(
        default=None,
        max_length=24,
        description="sattelite name",
    )
