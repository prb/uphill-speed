"""CLI entry point for the GPX Segment Report application."""

from __future__ import annotations

import argparse
import os
import sys

from gpx_segment_report.chart import generate_chart
from gpx_segment_report.converter import (
    METERS_TO_FEET,
    convert_elevation,
    default_min_height,
)
from gpx_segment_report.formatter import format_report
from gpx_segment_report.models import (
    ElevationUnit,
    GpxParseError,
    SUPPORTED_SPORTS,
)
from gpx_segment_report.parser import parse_gpx
from gpx_segment_report.pitch import compute_all_pitches
from gpx_segment_report.segments import (
    DEFAULT_FLATNESS_THRESHOLD,
    DEFAULT_MIN_TRIM_DURATION,
    DEFAULT_TIME_WINDOW,
    identify_segments,
)


def main() -> None:
    """Parse arguments and run the GPX segment report pipeline."""
    parser = argparse.ArgumentParser(
        description="Generate a segment report from a GPX 1.1 track file.",
    )
    parser.add_argument("file", help="Path to the GPX file")
    parser.add_argument(
        "--unit",
        "-u",
        choices=["feet", "meters"],
        default="feet",
        help="Elevation unit for the report (default: feet)",
    )
    parser.add_argument(
        "--min-height",
        "-m",
        type=float,
        default=None,
        help="Minimum elevation change in PRL units to qualify as a segment",
    )
    parser.add_argument(
        "--sport",
        "-s",
        default="ski_touring",
        help=(
            "Sport profile name; controls whether interior flats merge "
            "into the surrounding climb (ski_touring) or split it into "
            "separate segments (trail_running) "
            "(default: ski_touring)"
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Save an elevation profile chart to this file path (.png or .svg)",
    )
    parser.add_argument(
        "--flatness-threshold",
        "-f",
        type=float,
        default=None,
        help=(
            "Max elevation range (in the chosen unit) over a window for it "
            "to count as flat; lower values detect subtler flats "
            "(default: ~10 ft / 3 m)"
        ),
    )
    parser.add_argument(
        "--time-window",
        "-w",
        type=float,
        default=DEFAULT_TIME_WINDOW,
        help=(
            "Sliding-window duration in seconds used to test flatness "
            f"(default: {DEFAULT_TIME_WINDOW:.0f})"
        ),
    )
    parser.add_argument(
        "--min-trim-duration",
        "-t",
        type=float,
        default=DEFAULT_MIN_TRIM_DURATION,
        help=(
            "Minimum duration in seconds a flat stretch must span to be "
            f"trimmed or split out (default: {DEFAULT_MIN_TRIM_DURATION:.0f})"
        ),
    )
    args = parser.parse_args()

    try:
        unit = ElevationUnit(args.unit)

        # Validate sport profile
        if args.sport not in SUPPORTED_SPORTS:
            supported = ", ".join(sorted(SUPPORTED_SPORTS))
            raise ValueError(
                f"Unsupported sport profile '{args.sport}'. "
                f"Supported: {supported}"
            )
        sport_profile = SUPPORTED_SPORTS[args.sport]

        # Determine min_height in meters
        if args.min_height is not None:
            min_height_prl = args.min_height
            if unit is ElevationUnit.FEET:
                min_height_meters = min_height_prl / METERS_TO_FEET
            else:
                min_height_meters = min_height_prl
        else:
            min_height_prl = default_min_height(unit)
            if unit is ElevationUnit.FEET:
                min_height_meters = min_height_prl / METERS_TO_FEET
            else:
                min_height_meters = min_height_prl

        # Determine flatness_threshold in meters (shares --unit with --min-height).
        if args.flatness_threshold is not None:
            if args.flatness_threshold < 0:
                raise ValueError("--flatness-threshold must be non-negative")
            if unit is ElevationUnit.FEET:
                flatness_threshold_meters = args.flatness_threshold / METERS_TO_FEET
            else:
                flatness_threshold_meters = args.flatness_threshold
        else:
            flatness_threshold_meters = DEFAULT_FLATNESS_THRESHOLD

        if args.time_window <= 0:
            raise ValueError("--time-window must be positive")
        if args.min_trim_duration < 0:
            raise ValueError("--min-trim-duration must be non-negative")

        points = parse_gpx(args.file)
        segments = identify_segments(
            points,
            min_height_meters,
            sport_profile,
            flatness_threshold=flatness_threshold_meters,
            time_window=args.time_window,
            min_trim_duration=args.min_trim_duration,
        )
        pitches = compute_all_pitches(segments)
        report = format_report(segments, unit, pitches=pitches)
        print(report)

        if args.output is not None:
            generate_chart(
                points, segments, unit, args.output,
                os.path.basename(args.file), pitches=pitches,
            )

    except (GpxParseError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
