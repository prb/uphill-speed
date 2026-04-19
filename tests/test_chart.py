"""Property-based tests for the chart module."""

import math
import uuid
from datetime import datetime, timedelta, timezone

import matplotlib.dates as mdates
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from gpx_segment_report.chart import FIGURE_HEIGHT, FIGURE_WIDTH, SUPPORTED_FORMATS, _build_figure, generate_chart
from gpx_segment_report.converter import convert_elevation
from gpx_segment_report.models import ElevationUnit, Segment, SegmentType, TrackPoint


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_BASE_TIME = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _trackpoints_strategy(
    min_size: int = 1, max_size: int = 50
) -> st.SearchStrategy[list[TrackPoint]]:
    """Generate a list of TrackPoints with unique, ordered timestamps."""
    return st.lists(
        st.floats(min_value=-500.0, max_value=9000.0, allow_nan=False, allow_infinity=False),
        min_size=min_size,
        max_size=max_size,
    ).flatmap(
        lambda elevs: st.lists(
            st.integers(min_value=1, max_value=600),
            min_size=len(elevs),
            max_size=len(elevs),
        ).map(
            lambda gaps: _build_trackpoints(elevs, gaps)
        )
    )


def _build_trackpoints(
    elevations: list[float], gaps: list[int]
) -> list[TrackPoint]:
    """Build ordered TrackPoints from elevations and time gaps."""
    points: list[TrackPoint] = []
    current = _BASE_TIME
    for elev, gap in zip(elevations, gaps):
        current = current + timedelta(seconds=gap)
        points.append(TrackPoint(timestamp=current, elevation=elev))
    return points


# ---------------------------------------------------------------------------
# Property 1: Plotted data correctness
# ---------------------------------------------------------------------------


# Feature: graphical-output, Property 1: Plotted data correctness
@given(
    points=_trackpoints_strategy(min_size=1, max_size=50),
    unit=st.sampled_from([ElevationUnit.FEET, ElevationUnit.METERS]),
)
@settings(max_examples=100)
def test_plotted_data_correctness(
    points: list[TrackPoint], unit: ElevationUnit
) -> None:
    """The elevation line has one y-value per track point, each matching
    convert_elevation(point.elevation, unit) within floating-point tolerance.

    **Validates: Requirements 1.1, 1.4, 1.5**
    """
    fig = _build_figure(points, segments=[], unit=unit, gpx_filename="test.gpx")
    ax = fig.get_axes()[0]

    y_data = ax.get_lines()[0].get_ydata()

    # Length must equal number of track points
    assert len(y_data) == len(points), (
        f"Expected {len(points)} y-values, got {len(y_data)}"
    )

    # Each y-value must match the converted elevation
    for i, (y_val, pt) in enumerate(zip(y_data, points)):
        expected = convert_elevation(pt.elevation, unit)
        assert math.isclose(y_val, expected, rel_tol=1e-9, abs_tol=1e-9), (
            f"Point {i}: y_val={y_val}, expected={expected}"
        )


# ---------------------------------------------------------------------------
# Segment generation strategy
# ---------------------------------------------------------------------------


@st.composite
def _segments_strategy(
    draw: st.DrawFn,
) -> tuple[list[TrackPoint], list[Segment]]:
    """Generate track points (>=4) and non-overlapping contiguous segments.

    Returns a tuple of (all_points, segments) where each segment's points
    are a contiguous slice of all_points with at least 2 points.
    """
    points = draw(_trackpoints_strategy(min_size=4, max_size=50))
    n = len(points)

    # Decide how many segments to create (at least 1)
    max_segments = n // 2  # each segment needs >= 2 points
    num_segments = draw(st.integers(min_value=1, max_value=max(1, min(max_segments, 5))))

    # Generate non-overlapping slice boundaries
    # We need num_segments slices, each with >= 2 points, within [0, n)
    # Strategy: pick sorted cut points to define slices
    segments: list[Segment] = []
    used = 0

    for i in range(num_segments):
        remaining_segments = num_segments - i
        remaining_points = n - used
        # Need at least 2 points per remaining segment
        if remaining_points < remaining_segments * 2:
            break

        # Start of this segment
        max_start = n - remaining_segments * 2 - used
        offset = draw(st.integers(min_value=0, max_value=max(0, max_start)))
        start = used + offset

        # Length of this segment (at least 2)
        min_end = start + 2
        # Leave room for remaining segments
        max_end = n - (remaining_segments - 1) * 2
        end = draw(st.integers(min_value=min_end, max_value=max(min_end, max_end)))

        seg_type = draw(st.sampled_from([SegmentType.ASCENT, SegmentType.DESCENT]))
        seg_points = tuple(points[start:end])
        segments.append(Segment(segment_type=seg_type, points=seg_points))

        used = end

    return points, segments


# ---------------------------------------------------------------------------
# Property 2: Segment overlay correspondence
# ---------------------------------------------------------------------------


# Feature: graphical-output, Property 2: Segment overlay correspondence
@given(data=_segments_strategy())
@settings(max_examples=100)
def test_segment_overlay_correspondence(
    data: tuple[list[TrackPoint], list[Segment]],
) -> None:
    """One PolyCollection per segment, each spanning the correct time range.

    **Validates: Requirements 2.1, 2.3**
    """
    points, segments = data

    fig = _build_figure(
        points, segments=segments, unit=ElevationUnit.METERS, gpx_filename="test.gpx"
    )
    ax = fig.get_axes()[0]

    collections = ax.collections

    # One PolyCollection per segment
    assert len(collections) == len(segments), (
        f"Expected {len(segments)} PolyCollection(s), got {len(collections)}"
    )

    for i, (coll, seg) in enumerate(zip(collections, segments)):
        # Get the x-coordinates from the PolyCollection paths
        paths = coll.get_paths()
        # fill_between creates a single path per call
        assert len(paths) == 1, (
            f"Segment {i}: expected 1 path, got {len(paths)}"
        )

        vertices = paths[0].vertices
        # x-values are matplotlib date numbers
        x_vals = vertices[:, 0]
        x_min = x_vals.min()
        x_max = x_vals.max()

        # Convert back to datetimes for comparison
        dt_min = mdates.num2date(x_min)
        dt_max = mdates.num2date(x_max)

        seg_start = seg.start_time
        seg_end = seg.end_time

        # Compare as timestamps (seconds) to avoid timezone object mismatch
        assert abs(dt_min.timestamp() - seg_start.timestamp()) < 1.0, (
            f"Segment {i}: x_min {dt_min} != segment start {seg_start}"
        )
        assert abs(dt_max.timestamp() - seg_end.timestamp()) < 1.0, (
            f"Segment {i}: x_max {dt_max} != segment end {seg_end}"
        )


# ---------------------------------------------------------------------------
# Mixed-segment strategy (guarantees at least one ascent and one descent)
# ---------------------------------------------------------------------------


@st.composite
def _mixed_segments_strategy(
    draw: st.DrawFn,
) -> tuple[list[TrackPoint], list[Segment]]:
    """Generate track points and segments with at least one ascent and one descent.

    Uses _segments_strategy and filters to ensure both segment types are present.
    """
    points = draw(_trackpoints_strategy(min_size=8, max_size=50))
    n = len(points)

    max_segments = n // 2
    num_segments = draw(st.integers(min_value=2, max_value=max(2, min(max_segments, 5))))

    segments: list[Segment] = []
    used = 0

    for i in range(num_segments):
        remaining_segments = num_segments - i
        remaining_points = n - used
        if remaining_points < remaining_segments * 2:
            break

        max_start = n - remaining_segments * 2 - used
        offset = draw(st.integers(min_value=0, max_value=max(0, max_start)))
        start = used + offset

        min_end = start + 2
        max_end = n - (remaining_segments - 1) * 2
        end = draw(st.integers(min_value=min_end, max_value=max(min_end, max_end)))

        seg_type = draw(st.sampled_from([SegmentType.ASCENT, SegmentType.DESCENT]))
        seg_points = tuple(points[start:end])
        segments.append(Segment(segment_type=seg_type, points=seg_points))

        used = end

    has_ascent = any(s.segment_type is SegmentType.ASCENT for s in segments)
    has_descent = any(s.segment_type is SegmentType.DESCENT for s in segments)

    # Force both types: flip the first segment that doesn't match the missing type
    if not has_ascent and len(segments) >= 2:
        seg = segments[0]
        segments[0] = Segment(segment_type=SegmentType.ASCENT, points=seg.points)
    if not has_descent and len(segments) >= 2:
        seg = segments[-1]
        segments[-1] = Segment(segment_type=SegmentType.DESCENT, points=seg.points)

    return points, segments


# ---------------------------------------------------------------------------
# Property 3: Segment overlay color consistency
# ---------------------------------------------------------------------------


# Feature: graphical-output, Property 3: Segment overlay color consistency
@given(data=_mixed_segments_strategy())
@settings(max_examples=100)
def test_segment_overlay_color_consistency(
    data: tuple[list[TrackPoint], list[Segment]],
) -> None:
    """All ascent overlays share one fill color, all descent overlays share
    a different fill color, and the two colors are distinct.

    **Validates: Requirements 2.2**
    """
    points, segments = data

    fig = _build_figure(
        points, segments=segments, unit=ElevationUnit.METERS, gpx_filename="test.gpx"
    )
    ax = fig.get_axes()[0]

    collections = ax.collections
    assert len(collections) == len(segments)

    ascent_colors: list[tuple[float, ...]] = []
    descent_colors: list[tuple[float, ...]] = []

    for coll, seg in zip(collections, segments):
        # get_facecolor() returns an Nx4 RGBA array; take the first row
        rgba = tuple(coll.get_facecolor()[0][:3])  # RGB only
        if seg.segment_type is SegmentType.ASCENT:
            ascent_colors.append(rgba)
        else:
            descent_colors.append(rgba)

    # Must have at least one of each (guaranteed by strategy)
    assert len(ascent_colors) >= 1, "Expected at least one ascent segment"
    assert len(descent_colors) >= 1, "Expected at least one descent segment"

    # All ascent overlays share the same RGB color
    for i, c in enumerate(ascent_colors):
        assert c == ascent_colors[0], (
            f"Ascent overlay {i} color {c} != first ascent color {ascent_colors[0]}"
        )

    # All descent overlays share the same RGB color
    for i, c in enumerate(descent_colors):
        assert c == descent_colors[0], (
            f"Descent overlay {i} color {c} != first descent color {descent_colors[0]}"
        )

    # Ascent and descent colors are distinct
    assert ascent_colors[0] != descent_colors[0], (
        f"Ascent color {ascent_colors[0]} must differ from descent color {descent_colors[0]}"
    )


# ---------------------------------------------------------------------------
# Property 7: Chart title contains filename
# ---------------------------------------------------------------------------


# Feature: graphical-output, Property 7: Chart title contains filename
@given(
    filename=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    ),
    points=_trackpoints_strategy(min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_chart_title_contains_filename(
    filename: str, points: list[TrackPoint]
) -> None:
    """The chart title must contain the GPX filename string passed to _build_figure.

    **Validates: Requirements 5.1**
    """
    fig = _build_figure(
        points, segments=[], unit=ElevationUnit.METERS, gpx_filename=filename
    )
    ax = fig.get_axes()[0]

    title = ax.get_title()
    assert filename in title, (
        f"Expected filename {filename!r} in title {title!r}"
    )


# ---------------------------------------------------------------------------
# Property 8: Figure size invariant
# ---------------------------------------------------------------------------


# Feature: graphical-output, Property 8: Figure size invariant
@given(
    points=_trackpoints_strategy(min_size=1, max_size=10),
    unit=st.sampled_from([ElevationUnit.FEET, ElevationUnit.METERS]),
    filename=st.text(
        min_size=1,
        max_size=30,
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    ),
)
@settings(max_examples=100)
def test_figure_size_invariant(
    points: list[TrackPoint], unit: ElevationUnit, filename: str
) -> None:
    """The rendered figure must always be 12 inches wide by 6 inches tall,
    regardless of input data.

    **Validates: Requirements 5.2**
    """
    fig = _build_figure(
        points, segments=[], unit=unit, gpx_filename=filename
    )

    width, height = tuple(fig.get_size_inches())
    assert width == FIGURE_WIDTH, (
        f"Expected figure width {FIGURE_WIDTH}, got {width}"
    )
    assert height == FIGURE_HEIGHT, (
        f"Expected figure height {FIGURE_HEIGHT}, got {height}"
    )


# ---------------------------------------------------------------------------
# Property 4: Output file format correctness
# ---------------------------------------------------------------------------


# Feature: graphical-output, Property 4: Output file format correctness
_property4_counter = 0


@given(
    points=_trackpoints_strategy(min_size=2, max_size=10),
)
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
def test_output_file_format_correctness(
    points: list[TrackPoint], tmp_path: object
) -> None:
    """PNG files start with the PNG magic bytes and SVG files contain <svg markup.

    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    from pathlib import Path

    global _property4_counter
    _property4_counter += 1
    suffix = _property4_counter

    tmp = Path(str(tmp_path))

    # Test PNG output
    png_path = tmp / f"chart_{suffix}.png"
    generate_chart(
        points=points,
        segments=[],
        unit=ElevationUnit.METERS,
        output_path=str(png_path),
        gpx_filename="test.gpx",
    )
    png_bytes = png_path.read_bytes()
    assert png_bytes[:4] == b"\x89PNG", (
        f"PNG file should start with \\x89PNG magic bytes, got {png_bytes[:4]!r}"
    )

    # Test SVG output
    svg_path = tmp / f"chart_{suffix}.svg"
    generate_chart(
        points=points,
        segments=[],
        unit=ElevationUnit.METERS,
        output_path=str(svg_path),
        gpx_filename="test.gpx",
    )
    svg_content = svg_path.read_text()
    assert "<svg" in svg_content, (
        "SVG file should contain <svg markup"
    )


# ---------------------------------------------------------------------------
# Property 5: Unsupported extension rejection
# ---------------------------------------------------------------------------


# Feature: graphical-output, Property 5: Unsupported extension rejection
@given(
    ext=st.from_regex(r"\.[a-z]{1,5}", fullmatch=True).filter(
        lambda ext: ext not in SUPPORTED_FORMATS
    ),
)
@settings(max_examples=100)
def test_unsupported_extension_rejection(ext: str) -> None:
    """generate_chart raises ValueError for any extension not in SUPPORTED_FORMATS,
    and the error message lists the supported formats.

    **Validates: Requirements 3.4**
    """
    import pytest

    # Minimal fixed track data — we're testing validation, not rendering
    base = _BASE_TIME + timedelta(seconds=1)
    points = [
        TrackPoint(timestamp=base, elevation=100.0),
        TrackPoint(timestamp=base + timedelta(seconds=10), elevation=110.0),
    ]

    output_path = f"/tmp/chart{ext}"

    with pytest.raises(ValueError, match="Unsupported output format"):
        generate_chart(
            points=points,
            segments=[],
            unit=ElevationUnit.METERS,
            output_path=output_path,
            gpx_filename="test.gpx",
        )


# ---------------------------------------------------------------------------
# Property 6: Missing directory rejection
# ---------------------------------------------------------------------------


# Feature: graphical-output, Property 6: Missing directory rejection
@given(
    dir_name=st.text(
        min_size=5,
        max_size=20,
        alphabet=st.characters(whitelist_categories=("L", "N")),
    ),
    ext=st.sampled_from([".png", ".svg"]),
)
@settings(max_examples=100)
def test_missing_directory_rejection(dir_name: str, ext: str) -> None:
    """generate_chart raises ValueError when the output path's parent directory
    does not exist, with a message indicating the directory was not found.

    **Validates: Requirements 3.5**
    """
    # Build a path under a non-existent parent using a UUID to guarantee uniqueness
    nonexistent_dir = f"/tmp/{uuid.uuid4().hex}_{dir_name}"
    output_path = f"{nonexistent_dir}/chart{ext}"

    # Minimal fixed track data — we're testing validation, not rendering
    base = _BASE_TIME + timedelta(seconds=1)
    points = [
        TrackPoint(timestamp=base, elevation=100.0),
        TrackPoint(timestamp=base + timedelta(seconds=10), elevation=110.0),
    ]

    with pytest.raises(ValueError, match="Output directory not found"):
        generate_chart(
            points=points,
            segments=[],
            unit=ElevationUnit.METERS,
            output_path=output_path,
            gpx_filename="test.gpx",
        )


# ---------------------------------------------------------------------------
# Unit tests for chart module (Task 4.4)
# ---------------------------------------------------------------------------


def _make_sample_points() -> list[TrackPoint]:
    """Create a small fixed set of track points for unit tests."""
    return _build_trackpoints(
        elevations=[100.0, 200.0, 150.0, 300.0],
        gaps=[10, 20, 30, 40],
    )


class TestYAxisLabel:
    """Y-axis label contains the correct unit string (Req 1.2)."""

    def test_ylabel_contains_feet(self) -> None:
        points = _make_sample_points()
        fig = _build_figure(points, segments=[], unit=ElevationUnit.FEET, gpx_filename="test.gpx")
        ax = fig.get_axes()[0]
        assert "feet" in ax.get_ylabel().lower()

    def test_ylabel_contains_meters(self) -> None:
        points = _make_sample_points()
        fig = _build_figure(points, segments=[], unit=ElevationUnit.METERS, gpx_filename="test.gpx")
        ax = fig.get_axes()[0]
        assert "meters" in ax.get_ylabel().lower()


class TestLegend:
    """Legend includes Ascent and Descent entries (Req 2.5)."""

    def test_legend_present_with_ascent_and_descent(self) -> None:
        points = _make_sample_points()
        fig = _build_figure(points, segments=[], unit=ElevationUnit.METERS, gpx_filename="test.gpx")
        ax = fig.get_axes()[0]
        legend = ax.get_legend()
        assert legend is not None
        labels = [t.get_text() for t in legend.get_texts()]
        assert "Ascent" in labels
        assert "Descent" in labels


class TestEmptySegments:
    """Chart renders without overlays when segments list is empty (Req 2.4)."""

    def test_no_overlays_with_empty_segments(self) -> None:
        points = _make_sample_points()
        fig = _build_figure(points, segments=[], unit=ElevationUnit.METERS, gpx_filename="test.gpx")
        ax = fig.get_axes()[0]
        assert len(ax.collections) == 0


class TestGrid:
    """Grid is enabled on axes (Req 5.4)."""

    def test_grid_enabled(self) -> None:
        points = _make_sample_points()
        fig = _build_figure(points, segments=[], unit=ElevationUnit.METERS, gpx_filename="test.gpx")
        ax = fig.get_axes()[0]
        assert ax.xaxis.get_gridlines()[0].get_visible() is True
        assert ax.yaxis.get_gridlines()[0].get_visible() is True
