from datetime import datetime
from typing import ClassVar

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKey,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .basemodel import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SatelliteMetadata(TimestampMixin, Base):
    __tablename__ = "satellite_metadata"

    norad_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=False
    )
    cospar_id: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    classification: Mapped[str] = mapped_column(
        CHAR(1), server_default="U", nullable=False
    )

    launch_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    tle_history: Mapped[list["TLEHistory"]] = relationship(
        back_populates="satellite", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("norad_id > 0", name="check_positive_norad_id"),
        CheckConstraint("launch_year >= 1957", name="check_valid_launch_year"),
        UniqueConstraint("cospar_id", name="uq_satellite_cospar_id"),
    )


class TLEHistory(Base):
    __tablename__ = "tle_history"

    norad_id: Mapped[int] = mapped_column(
        ForeignKey("satellite_metadata.norad_id", ondelete="CASCADE"),
        primary_key=True,
    )
    epoch_timestamp: Mapped[datetime] = mapped_column(primary_key=True)
    element_set_number: Mapped[int] = mapped_column(nullable=False)
    raw_line1: Mapped[str] = mapped_column(CHAR(69), nullable=False)
    raw_line2: Mapped[str] = mapped_column(CHAR(69), nullable=False)

    captured_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    spacecraft: Mapped["SatelliteMetadata"] = relationship(
        back_populates="tle_history"
    )

    __table_args__: ClassVar[dict] = {
        "postgresql_partition_by": "RANGE (epoch_timestamp)"
    }
