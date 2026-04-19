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
from gpx_segment_report.segments import identify_segments


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
        help="Sport profile name (default: ski_touring)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Save an elevation profile chart to this file path (.png or .svg)",
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

        points = parse_gpx(args.file)
        segments = identify_segments(points, min_height_meters, sport_profile)
        report = format_report(segments, unit)
        print(report)

        if args.output is not None:
            generate_chart(
                points, segments, unit, args.output, os.path.basename(args.file)
            )

    except (GpxParseError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
