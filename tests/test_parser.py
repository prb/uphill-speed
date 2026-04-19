"""Property-based tests for the GPX parser.

Feature: gpx-segment-report, Property 1: Parser round-trip preserves track points
Validates: Requirements 1.1, 1.2
"""

from __future__ import annotations

import math
import tempfile
from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

import pytest

from gpx_segment_report.models import GpxParseError
from gpx_segment_report.parser import parse_gpx


# --- Strategies ---

_base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

_elevations = st.floats(min_value=-500.0, max_value=9000.0, allow_nan=False, allow_infinity=False)

_timestamp_offsets = st.integers(min_value=0, max_value=365 * 24 * 3600)


@st.composite
def _track_point_data(draw: st.DrawFn) -> tuple[datetime, float]:
    """Draw a single (timestamp, elevation) pair."""
    offset = draw(_timestamp_offsets)
    ts = _base_time + timedelta(seconds=offset)
    ele = draw(_elevations)
    return ts, ele


_track_point_lists = st.lists(
    _track_point_data(),
    min_size=1,
    max_size=50,
).map(lambda pts: sorted(pts, key=lambda p: p[0]))


# --- Helpers ---


def _build_gpx_xml(points: list[tuple[datetime, float]]) -> str:
    """Construct a minimal valid GPX 1.1 XML string from (timestamp, elevation) pairs."""
    trkpts = "\n".join(
        f'        <trkpt lat="0" lon="0">'
        f"<ele>{ele}</ele>"
        f"<time>{ts.strftime('%Y-%m-%dT%H:%M:%SZ')}</time>"
        f"</trkpt>"
        for ts, ele in points
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="test">\n'
        "  <trk>\n"
        "    <trkseg>\n"
        f"{trkpts}\n"
        "    </trkseg>\n"
        "  </trk>\n"
        "</gpx>"
    )


# --- Property test ---


@given(points=_track_point_lists)
@settings(max_examples=200)
def test_parser_round_trip_preserves_track_points(
    points: list[tuple[datetime, float]],
) -> None:
    """Parsing GPX XML built from (timestamp, elevation) pairs returns matching TrackPoints.

    Property 1: For any sequence of (timestamp, elevation) pairs used to construct
    a valid GPX 1.1 XML string, parsing that string should return TrackPoint values
    with the same timestamps in the same order and the same elevation values (within
    floating-point tolerance).
    """
    gpx_xml = _build_gpx_xml(points)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
        f.write(gpx_xml)
        tmp_path = f.name

    result = parse_gpx(tmp_path)

    assert len(result) == len(points)

    for track_point, (expected_ts, expected_ele) in zip(result, points):
        # Timestamps should match (both are UTC)
        assert track_point.timestamp.replace(tzinfo=timezone.utc) == expected_ts
        # Elevations should be close (XML serialization may lose some precision)
        assert math.isclose(
            track_point.elevation, expected_ele, rel_tol=1e-6, abs_tol=1e-9
        )


# --- Strategies for Property 2 ---


def _build_gpx_xml_with_missing_ele(
    points: list[tuple[datetime, float]],
    missing_indices: set[int],
) -> str:
    """Build GPX XML where points at *missing_indices* have no <ele> element."""
    trkpts: list[str] = []
    for i, (ts, ele) in enumerate(points):
        time_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        if i in missing_indices:
            trkpts.append(
                f'        <trkpt lat="0" lon="0">'
                f"<time>{time_str}</time>"
                f"</trkpt>"
            )
        else:
            trkpts.append(
                f'        <trkpt lat="0" lon="0">'
                f"<ele>{ele}</ele>"
                f"<time>{time_str}</time>"
                f"</trkpt>"
            )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="test">\n'
        "  <trk>\n"
        "    <trkseg>\n"
        + "\n".join(trkpts)
        + "\n"
        "    </trkseg>\n"
        "  </trk>\n"
        "</gpx>"
    )


@st.composite
def _points_with_missing_elevation(
    draw: st.DrawFn,
) -> tuple[list[tuple[datetime, float]], set[int]]:
    """Generate track points and choose at least one index to strip elevation from."""
    points = draw(_track_point_lists)
    indices = range(len(points))
    missing = draw(
        st.sets(st.sampled_from(list(indices)), min_size=1, max_size=len(points))
    )
    return points, missing


# --- Property 2 test ---


@given(data=_points_with_missing_elevation())
@settings(max_examples=200)
def test_parser_rejects_missing_elevation(
    data: tuple[list[tuple[datetime, float]], set[int]],
) -> None:
    """Parser raises GpxParseError when any track point lacks elevation.

    Property 2: For any GPX XML string where one or more track points lack
    an <ele> element, parse_gpx should raise a GpxParseError.
    Validates: Requirements 1.3
    """
    points, missing_indices = data

    gpx_xml = _build_gpx_xml_with_missing_ele(points, missing_indices)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
        f.write(gpx_xml)
        tmp_path = f.name

    with pytest.raises(GpxParseError, match="missing elevation data"):
        parse_gpx(tmp_path)


# --- Unit tests for parser error cases (Task 4.4) ---
# Validates: Requirements 1.3, 1.4, 7.1, 7.2


def test_nonexistent_file_raises_gpx_parse_error() -> None:
    """A non-existent file path should raise GpxParseError."""
    with pytest.raises(GpxParseError, match="File not found"):
        parse_gpx("/tmp/does_not_exist_abc123.gpx")


def test_invalid_gpx_xml_raises_gpx_parse_error(tmp_path: object) -> None:
    """Malformed XML should raise GpxParseError."""
    import pathlib

    bad_file = pathlib.Path(str(tmp_path)) / "bad.gpx"
    bad_file.write_text("<<<this is not valid xml>>>", encoding="utf-8")

    with pytest.raises(GpxParseError, match="Invalid GPX file"):
        parse_gpx(str(bad_file))


def test_no_track_segments_raises_gpx_parse_error(tmp_path: object) -> None:
    """A GPX file with no track segments should raise GpxParseError."""
    import pathlib

    gpx_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="test">\n'
        "</gpx>"
    )
    empty_file = pathlib.Path(str(tmp_path)) / "empty.gpx"
    empty_file.write_text(gpx_xml, encoding="utf-8")

    with pytest.raises(GpxParseError, match="no track segments"):
        parse_gpx(str(empty_file))


def test_missing_timestamps_raises_gpx_parse_error(tmp_path: object) -> None:
    """Track points without timestamps should raise GpxParseError."""
    import pathlib

    gpx_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="test">\n'
        "  <trk>\n"
        "    <trkseg>\n"
        '      <trkpt lat="0" lon="0"><ele>100.0</ele></trkpt>\n'
        "    </trkseg>\n"
        "  </trk>\n"
        "</gpx>"
    )
    no_time_file = pathlib.Path(str(tmp_path)) / "no_time.gpx"
    no_time_file.write_text(gpx_xml, encoding="utf-8")

    with pytest.raises(GpxParseError, match="missing timestamp data"):
        parse_gpx(str(no_time_file))
