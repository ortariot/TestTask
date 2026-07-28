from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sgp4.api import Satrec


class TLEData(BaseModel):
    content: Literal["tle"] = "tle"

    line1: str = Field(
        ...,
        min_length=69,
        max_length=69,
        description="first TLE",
        examples=[
            "1 25544U 98067A   24089.70425714  .00014761  00000-0  26402-3 0  9997"  # noqa: E501
        ],
    )
    line2: str = Field(
        ...,
        min_length=69,
        max_length=69,
        description="second TLE",
        examples=[
            "2 25544  51.6416 195.8450 0004245 214.3989 240.2317 15.49509425445831"  # noqa: E501
        ],
    )
    name: str | None = Field(
        default=None,
        max_length=24,
        description="sattelite name",
    )

    @model_validator(mode="after")
    def validate_tle_via_sgp4(self) -> "TLEData":

        l1 = self.line1.strip()
        l2 = self.line2.strip()

        try:
            Satrec.twoline2rv(l1, l2)
        except ValueError as err:
            raise ValueError(f"Invalid TLE data: {err}") from err

        self.line1 = l1
        self.line2 = l2
        return self
