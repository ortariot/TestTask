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
        description="satellite name",
    )

    @staticmethod
    def _calculate_norad_checksum(line: str) -> int:

        checksum = 0

        for char in line[:68]:
            if char.isdigit():
                checksum += int(char)
            elif char == "-":
                checksum += 1
        return checksum % 10

    @model_validator(mode="after")
    def strict_tle_validation(self) -> TLEData:

        LINE_LENGTH = 69

        l1 = self.line1.strip().replace("\n", "").replace("\r", "")
        l2 = self.line2.strip().replace("\n", "").replace("\r", "")

        if len(l1) != LINE_LENGTH or len(l2) != LINE_LENGTH:
            raise ValueError(
                "TLE lines must be exactly 69 characters. "
                f"(L1: {len(l1)}, L2: {len(l2)})"
            )

        if not l1.startswith("1 ") or not l2.startswith("2 "):
            raise ValueError(
                "Line 1 must start with '1 ', and Line 2 — with '2 '"
            )

        if self._calculate_norad_checksum(l1) != int(l1[-1]):
            raise ValueError(
                "Invalid checksum for line 1. Expected: "
                f"{self._calculate_norad_checksum(l1)}, in line: {l1[-1]}"
            )

        if self._calculate_norad_checksum(l2) != int(l2[-1]):
            raise ValueError(
                f"Invalid checksum for line 2. Expected: "
                f"{self._calculate_norad_checksum(l2)}, in line: {l2[-1]}"
            )

        if l1[2:7] != l2[2:7]:
            raise ValueError(
                f"Satellite numbers do not match: {l1[2:7]} and {l2[2:7]}"
            )

        try:
            Satrec.twoline2rv(l1, l2)
        except ValueError as physics_err:
            raise ValueError(
                f"SGP4 mathematical model rejected the TLE: {physics_err}"
            ) from physics_err

        self.line1 = l1
        self.line2 = l2
        return self
