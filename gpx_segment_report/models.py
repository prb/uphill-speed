"""Data models and enums for the GPX Segment Report application."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ElevationUnit(Enum):
    """Elevation unit for report output."""

    FEET = "feet"
    METERS = "meters"


class SegmentType(Enum):
    """Classification of a track segment."""

    ASCENT = "ascent"
    DESCENT = "descent"


@dataclass(frozen=True)
class TrackPoint:
    """A single point from a GPX track."""

    timestamp: datetime
    elevation: float  # always stored in meters (native GPX unit)


@dataclass(frozen=True)
class Segment:
    """A coarse-grained ascending or descending segment."""

    segment_type: SegmentType
    points: tuple[TrackPoint, ...]  # ordered track points in this segment

    @property
    def start_time(self) -> datetime:
        return self.points[0].timestamp

    @property
    def end_time(self) -> datetime:
        return self.points[-1].timestamp

    @property
    def start_elevation(self) -> float:
        return self.points[0].elevation

    @property
    def end_elevation(self) -> float:
        return self.points[-1].elevation


@dataclass(frozen=True)
class SportProfile:
    """Sport-specific segmentation configuration."""

    name: str


SKI_TOURING = SportProfile(name="ski_touring")

SUPPORTED_SPORTS: dict[str, SportProfile] = {
    "ski_touring": SKI_TOURING,
}


class GpxParseError(Exception):
    """Raised when GPX parsing fails due to missing or invalid data."""
