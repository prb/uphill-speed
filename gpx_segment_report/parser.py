"""GPX file parser — extracts track points from GPX 1.1 files."""

from __future__ import annotations

import os

import gpxpy
import gpxpy.gpx

from gpx_segment_report.models import GpxParseError, TrackPoint


def parse_gpx(file_path: str) -> list[TrackPoint]:
    """Parse a GPX 1.1 file and return ordered track points.

    Iterates over all tracks, segments, and points in the file,
    extracting elevation and timestamp into TrackPoint values.

    Raises:
        GpxParseError: If the file is missing, invalid, lacks elevation
                       data, lacks timestamps, or contains no track segments.
    """
    if not os.path.exists(file_path):
        raise GpxParseError(f"File not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            gpx = gpxpy.parse(f)
    except gpxpy.gpx.GPXXMLSyntaxException as exc:
        raise GpxParseError(f"Invalid GPX file: {file_path}") from exc

    # Collect all segments across all tracks
    all_segments = [
        seg for track in gpx.tracks for seg in track.segments
    ]
    if not all_segments:
        raise GpxParseError("GPX file contains no track segments")

    track_points: list[TrackPoint] = []
    point_index = 0

    for segment in all_segments:
        for point in segment.points:
            if point.elevation is None:
                raise GpxParseError(
                    f"Track point at index {point_index} is missing elevation data"
                )
            if point.time is None:
                raise GpxParseError(
                    f"Track point at index {point_index} is missing timestamp data"
                )
            track_points.append(
                TrackPoint(timestamp=point.time, elevation=point.elevation)
            )
            point_index += 1

    return track_points
