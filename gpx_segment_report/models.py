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
    latitude: float  # decimal degrees
    longitude: float  # decimal degrees


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
    """Sport-specific segmentation configuration.

    Attributes:
        name: Identifier for the sport profile.
        merge_across_interior_gaps: When ``True``, same-direction segments
            separated by a trimmed interior flat stretch are merged back
            into a single segment.  This suits ski touring, where a flat
            traverse mid-climb is still part of the ascent.  When
            ``False``, interior flats stay as gaps that split the
            segment, which suits trail running.
    """

    name: str
    merge_across_interior_gaps: bool = True


SKI_TOURING = SportProfile(
    name="ski_touring",
    merge_across_interior_gaps=True,
)

TRAIL_RUNNING = SportProfile(
    name="trail_running",
    merge_across_interior_gaps=False,
)

SUPPORTED_SPORTS: dict[str, SportProfile] = {
    "ski_touring": SKI_TOURING,
    "trail_running": TRAIL_RUNNING,
}


class GpxParseError(Exception):
    """Raised when GPX parsing fails due to missing or invalid data."""
