"""Property-based tests for the report formatter."""

import re
from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from gpx_segment_report.formatter import format_report
from gpx_segment_report.models import ElevationUnit, Segment, SegmentType, TrackPoint


def _make_segment(
    seg_type: SegmentType,
    start_seconds: int,
    duration_seconds: int,
    start_elevation: float,
    end_elevation: float,
) -> Segment:
    """Build a Segment with two track points (start and end)."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    p_start = TrackPoint(
        timestamp=base + timedelta(seconds=start_seconds),
        elevation=start_elevation,
    )
    p_end = TrackPoint(
        timestamp=base + timedelta(seconds=start_seconds + duration_seconds),
        elevation=end_elevation,
    )
    return Segment(segment_type=seg_type, points=(p_start, p_end))


# Strategy: generate a valid segment with consistent type/elevation direction
_segment_strategy = (
    st.tuples(
        st.sampled_from([SegmentType.ASCENT, SegmentType.DESCENT]),
        st.integers(min_value=0, max_value=100_000),
        st.integers(min_value=1, max_value=36_000),
        st.floats(min_value=-2000.0, max_value=9000.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=10.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
    ).map(
        lambda t: _make_segment(
            seg_type=t[0],
            start_seconds=t[1],
            duration_seconds=t[2],
            start_elevation=t[3],
            end_elevation=t[3] + t[4] if t[0] == SegmentType.ASCENT else t[3] - t[4],
        )
    )
)


# Feature: gpx-segment-report, Property 9: Report row count and chronological order
@given(
    segments=st.lists(_segment_strategy, min_size=0, max_size=30),
    unit=st.sampled_from([ElevationUnit.FEET, ElevationUnit.METERS]),
)
@settings(max_examples=200)
def test_report_row_count_and_chronological_order(
    segments: list[Segment], unit: ElevationUnit
) -> None:
    """Report has exactly len(segments) data rows in chronological order."""
    report = format_report(segments, unit)
    lines = report.split("\n")

    # First line is always the header
    header = lines[0]
    data_rows = lines[1:]

    # Row count: exactly one data row per segment
    assert len(data_rows) == len(segments), (
        f"Expected {len(segments)} data rows, got {len(data_rows)}"
    )

    # Chronological order: start_time of each row must be non-decreasing
    if len(data_rows) >= 2:
        start_times = [
            datetime.fromisoformat(row.split("\t")[0]) for row in data_rows
        ]
        for i in range(1, len(start_times)):
            assert start_times[i] >= start_times[i - 1], (
                f"Row {i} start_time {start_times[i]} is before "
                f"row {i - 1} start_time {start_times[i - 1]}"
            )


_HH_MM_SS_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")


# Feature: gpx-segment-report, Property 10: Report rows contain all required fields
@given(
    segment=_segment_strategy,
    unit=st.sampled_from([ElevationUnit.FEET, ElevationUnit.METERS]),
)
@settings(max_examples=200)
def test_report_rows_contain_all_required_fields(
    segment: Segment, unit: ElevationUnit
) -> None:
    """Every report data row contains valid ISO 8601 timestamps, segment type,
    HH:MM:SS total time, start/end elevations, and rate."""
    report = format_report([segment], unit)
    lines = report.split("\n")
    assert len(lines) == 2, f"Expected header + 1 data row, got {len(lines)} lines"

    fields = lines[1].split("\t")
    assert len(fields) == 7, f"Expected 7 tab-separated fields, got {len(fields)}"

    start_time_str, end_time_str, seg_type, total_time, start_elev, end_elev, rate = fields

    # Valid ISO 8601 timestamps (datetime.fromisoformat will raise on invalid)
    datetime.fromisoformat(start_time_str)
    datetime.fromisoformat(end_time_str)

    # Segment type is one of the expected values
    assert seg_type in ("ascent", "descent"), f"Unexpected segment type: {seg_type}"

    # Total time matches HH:MM:SS pattern
    assert _HH_MM_SS_RE.match(total_time), f"total_time '{total_time}' is not HH:MM:SS"

    # Start/end elevations and rate are valid floats
    assert _FLOAT_RE.match(start_elev), f"start_elevation '{start_elev}' is not a valid float"
    assert _FLOAT_RE.match(end_elev), f"end_elevation '{end_elev}' is not a valid float"
    assert _FLOAT_RE.match(rate), f"rate '{rate}' is not a valid float"


# Feature: gpx-segment-report, Property 11: Report computation correctness
@given(
    segment=_segment_strategy,
    unit=st.sampled_from([ElevationUnit.FEET, ElevationUnit.METERS]),
)
@settings(max_examples=200)
def test_report_computation_correctness(
    segment: Segment, unit: ElevationUnit
) -> None:
    """total_time equals end_time - start_time as HH:MM:SS, and rate equals
    abs(elevation_change) / hours within tolerance."""
    report = format_report([segment], unit)
    lines = report.split("\n")
    fields = lines[1].split("\t")
    _, _, _, total_time, start_elev, end_elev, rate = fields

    # Verify total_time matches expected HH:MM:SS from segment timestamps
    duration_secs = (segment.end_time - segment.start_time).total_seconds()
    total_int = int(duration_secs)
    hours, remainder = divmod(total_int, 3600)
    minutes, secs = divmod(remainder, 60)
    expected_total_time = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    assert total_time == expected_total_time, (
        f"total_time '{total_time}' != expected '{expected_total_time}'"
    )

    # Verify rate equals abs(elevation_change) / hours within tolerance.
    # The formatter computes rate from full-precision converted elevations,
    # then rounds to one decimal place. We replicate that here.
    from gpx_segment_report.converter import convert_elevation

    start_elev_full = convert_elevation(segment.start_elevation, unit)
    end_elev_full = convert_elevation(segment.end_elevation, unit)
    rate_f = float(rate)
    hours_f = duration_secs / 3600.0
    if hours_f > 0:
        expected_rate = abs(end_elev_full - start_elev_full) / hours_f
        # Both values are rounded to 1 decimal place, so tolerance of 0.1
        assert abs(rate_f - round(expected_rate, 1)) < 0.15, (
            f"rate {rate_f} != expected {round(expected_rate, 1)} "
            f"(diff={abs(rate_f - round(expected_rate, 1)):.4f})"
        )
