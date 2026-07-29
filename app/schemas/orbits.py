from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class OrbitData(BaseModel):
    content: Literal["orbit"] = "orbit"

    object_name: str = Field(..., alias="OBJECT_NAME")
    object_id: str = Field(..., alias="OBJECT_ID")
    epoch: datetime = Field(..., alias="EPOCH")

    mean_motion: float = Field(..., alias="MEAN_MOTION", ge=0.0)
    eccentricity: float = Field(..., alias="ECCENTRICITY", ge=0.0, lt=1.0)
    inclination: float = Field(..., alias="INCLINATION", ge=0.0, le=180.0)
    ra_of_asc_node: float = Field(
        ..., alias="RA_OF_ASC_NODE", ge=0.0, le=360.0
    )
    arg_of_pericenter: float = Field(
        ..., alias="ARG_OF_PERICENTER", ge=0.0, le=360.0
    )
    mean_anomaly: float = Field(..., alias="MEAN_ANOMALY", ge=0.0, le=360.0)

    ephemeris_type: int = Field(default=0, alias="EPHEMERIS_TYPE")
    classification_type: str = Field(default="U", alias="CLASSIFICATION_TYPE")
    norad_cat_id: int = Field(..., alias="NORAD_CAT_ID")
    element_set_no: int = Field(default=999, alias="ELEMENT_SET_NO")
    rev_at_epoch: int = Field(..., alias="REV_AT_EPOCH")
    bstar: float = Field(default=0.0, alias="BSTAR")
    mean_motion_dot: float = Field(default=0.0, alias="MEAN_MOTION_DOT")
    mean_motion_ddot: float = Field(default=0.0, alias="MEAN_MOTION_DDOT")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def launch_year(self) -> int:

        BORDER_YEAR = 50
        PART_2 = 2
        PAER_5 = 5
        parts = self.object_id.split("-")
        year_str = parts[0].strip()

        if len(year_str) == PART_2 or (
            len(year_str) == PAER_5 and not year_str.startswith("20")
        ):
            short_year = int(year_str[:2])
            full_year = (
                1900 + short_year
                if short_year >= BORDER_YEAR
                else 2000 + short_year
            )
            return full_year

        return int(year_str[:4])

    model_config = {"populate_by_name": True}
