import enum
from datetime import datetime

from sqlalchemy import (
    BIGINT,
    CHAR,
    FLOAT,
    INTEGER,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.utils import enum_check_constraint

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
    cospar_id: Mapped[str] = mapped_column(String(15), nullable=False)
    classification: Mapped[str] = mapped_column(
        CHAR(1), server_default="U", nullable=False
    )

    launch_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    tle_history: Mapped[list["TLEHistory"]] = relationship(
        back_populates="satellite", cascade="all, delete-orphan"
    )

    orbit_history: Mapped[list["OrbitHistory"]] = relationship(
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
    raw_line1: Mapped[str] = mapped_column(CHAR(69), nullable=False)
    raw_line2: Mapped[str] = mapped_column(CHAR(69), nullable=False)

    satellite: Mapped["SatelliteMetadata"] = relationship(
        back_populates="tle_history"
    )


class OrbitHistory(Base):
    __tablename__ = "orbit_history"

    norad_cat_id: Mapped[int] = mapped_column(
        ForeignKey("satellite_metadata.norad_id", ondelete="CASCADE"),
        primary_key=True,
    )
    epoch: Mapped[datetime] = mapped_column(primary_key=True)

    object_name: Mapped[str] = mapped_column(nullable=False)
    object_id: Mapped[str] = mapped_column(nullable=False)

    mean_motion: Mapped[float] = mapped_column(FLOAT, nullable=False)
    eccentricity: Mapped[float] = mapped_column(FLOAT, nullable=False)
    inclination: Mapped[float] = mapped_column(FLOAT, nullable=False)
    ra_of_asc_node: Mapped[float] = mapped_column(FLOAT, nullable=False)
    arg_of_pericenter: Mapped[float] = mapped_column(FLOAT, nullable=False)
    mean_anomaly: Mapped[float] = mapped_column(FLOAT, nullable=False)

    ephemeris_type: Mapped[int] = mapped_column(
        INTEGER, server_default="0", nullable=False
    )
    classification_type: Mapped[str] = mapped_column(
        CHAR(1), server_default="U", nullable=False
    )
    element_set_no: Mapped[int] = mapped_column(
        INTEGER, server_default="999", nullable=False
    )
    rev_at_epoch: Mapped[int] = mapped_column(INTEGER, nullable=False)
    bstar: Mapped[float] = mapped_column(
        FLOAT, server_default="0.0", nullable=False
    )
    mean_motion_dot: Mapped[float] = mapped_column(
        FLOAT, server_default="0.0", nullable=False
    )
    mean_motion_ddot: Mapped[float] = mapped_column(
        FLOAT, server_default="0.0", nullable=False
    )

    satellite: Mapped["SatelliteMetadata"] = relationship(
        back_populates="orbit_history"
    )


class TaskStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class TaskType(enum.StrEnum):
    FAST = "fast"
    SLOW = "slow"
    PREC = "precision"


class CalculationTask(TimestampMixin, Base):
    __tablename__ = "calculation_tasks"

    id: Mapped[int] = mapped_column(
        BIGINT, primary_key=True, autoincrement=True
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_points: Mapped[int] = mapped_column(BIGINT, nullable=False)

    status: Mapped[TaskStatus] = mapped_column(
        String(20), default=TaskStatus.PENDING, nullable=False
    )

    task_type: Mapped[TaskType] = mapped_column(
        String(20), default=TaskType.SLOW, nullable=False
    )

    used_tle_norad_id: Mapped[int | None] = mapped_column(nullable=True)
    used_tle_epoch: Mapped[datetime | None] = mapped_column(nullable=True)

    used_orbit_norad_id: Mapped[int | None] = mapped_column(nullable=True)
    used_orbit_epoch: Mapped[datetime | None] = mapped_column(nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    chunks_total: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0
    )
    chunks_done: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0
    )

    # TODO error_message, rows_count

    __table_args__ = (
        Index("idx_tasks_status_created", "status", "created_at"),
        Index("idx_tasks_satellite", "used_tle_norad_id"),
        ForeignKeyConstraint(
            ["used_tle_norad_id", "used_tle_epoch"],
            ["tle_history.norad_id", "tle_history.epoch_timestamp"],
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["used_orbit_norad_id", "used_orbit_epoch"],
            ["orbit_history.norad_cat_id", "orbit_history.epoch"],
            ondelete="SET NULL",
        ),
        enum_check_constraint(TaskStatus, "status"),
        enum_check_constraint(TaskType, "task_type"),
        CheckConstraint("start_time <= end_time", name="ck_valid_time_range"),
        CheckConstraint(
            """
            (used_tle_norad_id IS NOT NULL AND used_tle_epoch IS NOT NULL
            AND used_orbit_norad_id IS NULL AND used_orbit_epoch IS NULL)
            OR
            (used_orbit_norad_id IS NOT NULL AND used_orbit_epoch IS NOT NULL
            AND used_tle_norad_id IS NULL AND used_tle_epoch IS NULL)
            """,
            name="ck_single_source_data",
        ),
    )
