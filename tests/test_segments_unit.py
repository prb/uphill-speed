"""Unit tests for edge cases and known shapes in segment identification."""

from datetime import datetime, timedelta, timezone

import pytest

from gpx_segment_report.models import SKI_TOURING, Segment, SegmentType, TrackPoint
from gpx_segment_report.segments import (
    _find_interior_flat_stretches,
    _is_window_flat,
    _merge_adjacent_same_direction,
    _perpendicular_distance,
    _split_interior_gaps,
    _trim_boundaries,
    _trim_segment_gaps,
    identify_segments,
)


def _make_track_points(elevations: list[float]) -> list[TrackPoint]:
    """Build a list of TrackPoint values with 1-second spacing."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        TrackPoint(timestamp=base + timedelta(seconds=i), elevation=e)
        for i, e in enumerate(elevations)
    ]


def _make_track_points_with_spacing(
    elevations: list[float], spacing: float
) -> list[TrackPoint]:
    """Build TrackPoint values with custom time spacing in seconds."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        TrackPoint(timestamp=base + timedelta(seconds=i * spacing), elevation=e)
        for i, e in enumerate(elevations)
    ]


# --- Edge cases ---


def test_empty_input() -> None:
    """0 points → []."""
    assert identify_segments([], 10.0, SKI_TOURING) == []


def test_single_point() -> None:
    """1 point → []."""
    points = _make_track_points([100.0])
    assert identify_segments(points, 10.0, SKI_TOURING) == []


def test_zero_min_height() -> None:
    """min_height=0 → []."""
    points = _make_track_points([0.0, 50.0, 100.0])
    assert identify_segments(points, 0.0, SKI_TOURING) == []


def test_negative_min_height() -> None:
    """min_height=-5 → []."""
    points = _make_track_points([0.0, 50.0, 100.0])
    assert identify_segments(points, -5.0, SKI_TOURING) == []


# --- Known shapes ---


def test_simple_v_shape() -> None:
    """V-shaped elevation → 1 descent + 1 ascent."""
    elevations = [100.0, 50.0, 0.0, 50.0, 100.0]
    points = _make_track_points(elevations)
    segments = identify_segments(points, 10.0, SKI_TOURING)

    assert len(segments) == 2
    assert segments[0].segment_type == SegmentType.DESCENT
    assert segments[1].segment_type == SegmentType.ASCENT


def test_simple_peak() -> None:
    """Peak-shaped elevation → 1 ascent + 1 descent."""
    elevations = [0.0, 50.0, 100.0, 50.0, 0.0]
    points = _make_track_points(elevations)
    segments = identify_segments(points, 10.0, SKI_TOURING)

    assert len(segments) == 2
    assert segments[0].segment_type == SegmentType.ASCENT
    assert segments[1].segment_type == SegmentType.DESCENT


# --- Filter and merge behaviour ---


def test_trivial_segment_filtered() -> None:
    """A small bump below min_height is discarded."""
    # Ascent of 5m then descent of 5m — both below min_height of 10
    elevations = [0.0, 5.0, 0.0]
    points = _make_track_points(elevations)
    segments = identify_segments(points, 10.0, SKI_TOURING)

    assert segments == []


def test_merge_after_filter() -> None:
    """Two ascents separated by a trivial descent merge into one ascent.

    Profile: 0 → 100 → 95 → 200
    The 5m descent between 100 and 95 is below min_height=10 and gets
    discarded, leaving two adjacent ascent candidates that merge.
    """
    elevations = [0.0, 100.0, 95.0, 200.0]
    points = _make_track_points(elevations)
    segments = identify_segments(points, 10.0, SKI_TOURING)

    assert len(segments) == 1
    assert segments[0].segment_type == SegmentType.ASCENT
    assert segments[0].start_elevation == 0.0
    assert segments[0].end_elevation == 200.0


# --- _perpendicular_distance degenerate case ---


def test_perpendicular_distance_degenerate() -> None:
    """When line_start == line_end, return Euclidean distance to the point."""
    origin = (0.0, 0.0)
    point = (3.0, 4.0)
    assert _perpendicular_distance(point, origin, origin) == pytest.approx(5.0)

    # Same point as the degenerate line → distance 0
    assert _perpendicular_distance(origin, origin, origin) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 8.1 — Boundary trimming scenarios
# ---------------------------------------------------------------------------


def test_trim_no_flat_stretches() -> None:
    """Segments with no flat regions pass through unchanged.

    A steeply ascending segment where every point-to-point change exceeds
    the flatness threshold should not be trimmed at all.
    Requirements: 1.1, 1.2
    """
    # 10 points, 30s apart, climbing 10m per step → every 60s window has
    # 20m range, well above flatness_threshold=3.0.
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    pts = tuple(
        TrackPoint(timestamp=base + timedelta(seconds=i * 30), elevation=100.0 + i * 10.0)
        for i in range(10)
    )
    seg = Segment(segment_type=SegmentType.ASCENT, points=pts)

    result = _trim_boundaries(seg, time_window=60.0, flatness_threshold=3.0, min_trim_duration=120.0)

    assert result is not None
    assert result.points == pts
    assert result.segment_type == SegmentType.ASCENT


def test_trim_leading_flat() -> None:
    """A known leading flat stretch is trimmed.

    Build a segment with a 180s flat prefix (elevation within 1m) followed
    by a steep ascent. The flat prefix exceeds min_trim_duration=120s and
    should be removed.
    Requirements: 1.1, 1.3
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Flat prefix: 7 points at 30s intervals → 180s, elevation ~100m.
    flat = [
        TrackPoint(timestamp=base + timedelta(seconds=i * 30), elevation=100.0 + (i % 2) * 0.5)
        for i in range(7)
    ]
    # Active ascent: 5 points continuing from t=210s, climbing steeply.
    active = [
        TrackPoint(timestamp=base + timedelta(seconds=210 + i * 10), elevation=120.0 + i * 20.0)
        for i in range(5)
    ]
    pts = tuple(flat + active)
    seg = Segment(segment_type=SegmentType.ASCENT, points=pts)

    result = _trim_boundaries(seg, time_window=60.0, flatness_threshold=3.0, min_trim_duration=120.0)

    assert result is not None
    # No flat points should remain.
    flat_ids = {id(p) for p in flat}
    for p in result.points:
        assert id(p) not in flat_ids, "Leading flat point was not trimmed"
    # All active points should be present.
    active_ids = {id(p) for p in active}
    for p in active:
        assert id(p) in {id(rp) for rp in result.points}, "Active point was lost"


def test_trim_trailing_flat() -> None:
    """A known trailing flat stretch is trimmed.

    Build a segment with a steep descent followed by a 180s flat suffix.
    Requirements: 1.2, 1.4
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Active descent: 5 points, 10s apart.
    active = [
        TrackPoint(timestamp=base + timedelta(seconds=i * 10), elevation=200.0 - i * 20.0)
        for i in range(5)
    ]
    # Flat suffix: 7 points at 30s intervals starting after active, elevation ~100m.
    t_start = 50
    flat = [
        TrackPoint(timestamp=base + timedelta(seconds=t_start + i * 30), elevation=100.0 + (i % 2) * 0.5)
        for i in range(7)
    ]
    pts = tuple(active + flat)
    seg = Segment(segment_type=SegmentType.DESCENT, points=pts)

    result = _trim_boundaries(seg, time_window=60.0, flatness_threshold=3.0, min_trim_duration=120.0)

    assert result is not None
    flat_ids = {id(p) for p in flat}
    for p in result.points:
        assert id(p) not in flat_ids, "Trailing flat point was not trimmed"
    active_ids = {id(p) for p in active}
    for p in active:
        assert id(p) in {id(rp) for rp in result.points}, "Active point was lost"


def test_trim_both_edges() -> None:
    """Both leading and trailing flat stretches are trimmed from the same segment.

    Requirements: 1.5
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t = 0.0
    # Leading flat: 7 points, 30s apart → 180s.
    lead_flat = []
    for i in range(7):
        lead_flat.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=100.0)
        )
        t += 30.0
    # Active ascent: 5 points, 10s apart.
    active = []
    for i in range(5):
        active.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=150.0 + i * 20.0)
        )
        t += 10.0
    # Trailing flat: 7 points, 30s apart → 180s.
    trail_flat = []
    trail_elev = active[-1].elevation + 50.0
    for i in range(7):
        trail_flat.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=trail_elev)
        )
        t += 30.0

    pts = tuple(lead_flat + active + trail_flat)
    seg = Segment(segment_type=SegmentType.ASCENT, points=pts)

    result = _trim_boundaries(seg, time_window=60.0, flatness_threshold=3.0, min_trim_duration=120.0)

    assert result is not None
    lead_ids = {id(p) for p in lead_flat}
    trail_ids = {id(p) for p in trail_flat}
    for p in result.points:
        assert id(p) not in lead_ids, "Leading flat point was not trimmed"
        assert id(p) not in trail_ids, "Trailing flat point was not trimmed"
    assert len(result.points) >= 2


def test_trim_consumes_segment() -> None:
    """An entirely flat segment is discarded (returns None).

    Requirements: 1.6
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # 10 points, 30s apart → 270s total, all at elevation 100m.
    pts = tuple(
        TrackPoint(timestamp=base + timedelta(seconds=i * 30), elevation=100.0)
        for i in range(10)
    )
    seg = Segment(segment_type=SegmentType.ASCENT, points=pts)

    result = _trim_boundaries(seg, time_window=60.0, flatness_threshold=3.0, min_trim_duration=120.0)

    assert result is None


# ---------------------------------------------------------------------------
# 8.2 — Interior splitting scenarios
# ---------------------------------------------------------------------------


def _build_ascent_flat_ascent_segment(
    min_trim_duration: float = 120.0,
    time_window: float = 60.0,
    flatness_threshold: float = 3.0,
    min_height: float = 10.0,
) -> tuple[Segment, list[TrackPoint], list[TrackPoint], list[TrackPoint]]:
    """Helper: build a segment with active-ascent / interior-flat / active-ascent.

    Returns (segment, before_points, flat_points, after_points).
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t = 0.0

    # Active ascending bookend: 6 points, 10s apart, +20m per step.
    before: list[TrackPoint] = []
    for i in range(6):
        before.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=100.0 + i * 20.0)
        )
        t += 10.0

    # Interior flat: 8 points, 30s apart → 210s, elevation ~300m.
    flat: list[TrackPoint] = []
    flat_elev = before[-1].elevation + 10.0
    for i in range(8):
        flat.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=flat_elev + (i % 2) * 0.5)
        )
        t += 30.0

    # Active ascending bookend after flat: 6 points, 10s apart, +20m per step.
    after_start = flat[-1].elevation + 10.0
    after: list[TrackPoint] = []
    for i in range(6):
        after.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=after_start + i * 20.0)
        )
        t += 10.0

    pts = tuple(before + flat + after)
    seg = Segment(segment_type=SegmentType.ASCENT, points=pts)
    return seg, before, flat, after


def test_interior_split_single() -> None:
    """A single interior flat stretch splits the segment into two.

    Requirements: 2.1, 2.2
    """
    seg, before, flat, after = _build_ascent_flat_ascent_segment()

    result = _split_interior_gaps(
        seg, time_window=60.0, flatness_threshold=3.0,
        min_trim_duration=120.0, min_height=10.0,
    )

    assert len(result) >= 2, f"Expected ≥2 sub-segments, got {len(result)}"
    # Each sub-segment inherits the original classification.
    for sub in result:
        assert sub.segment_type == SegmentType.ASCENT


def test_interior_split_multiple() -> None:
    """Multiple interior flat stretches produce multiple sub-segments.

    Requirements: 2.5
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t = 0.0

    def _active_block(start_elev: float) -> list[TrackPoint]:
        nonlocal t
        pts = []
        for i in range(6):
            pts.append(
                TrackPoint(timestamp=base + timedelta(seconds=t), elevation=start_elev + i * 20.0)
            )
            t += 10.0
        return pts

    def _flat_block(elev: float) -> list[TrackPoint]:
        nonlocal t
        pts = []
        for i in range(8):
            pts.append(
                TrackPoint(timestamp=base + timedelta(seconds=t), elevation=elev)
            )
            t += 30.0
        return pts

    active1 = _active_block(100.0)
    flat1 = _flat_block(active1[-1].elevation + 10.0)
    active2 = _active_block(flat1[-1].elevation + 10.0)
    flat2 = _flat_block(active2[-1].elevation + 10.0)
    active3 = _active_block(flat2[-1].elevation + 10.0)

    pts = tuple(active1 + flat1 + active2 + flat2 + active3)
    seg = Segment(segment_type=SegmentType.ASCENT, points=pts)

    result = _split_interior_gaps(
        seg, time_window=60.0, flatness_threshold=3.0,
        min_trim_duration=120.0, min_height=10.0,
    )

    assert len(result) >= 3, f"Expected ≥3 sub-segments from 2 interior flats, got {len(result)}"


def test_split_discards_tiny_subsegment() -> None:
    """A sub-segment below min_height after split is discarded.

    Requirements: 2.4
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t = 0.0

    # Tiny active bookend: 3 points, only 4m total elevation change (< min_height=10).
    tiny_before: list[TrackPoint] = []
    for i in range(3):
        tiny_before.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=100.0 + i * 2.0)
        )
        t += 10.0

    # Interior flat: 8 points, 30s apart → 210s.
    flat: list[TrackPoint] = []
    flat_elev = 110.0
    for i in range(8):
        flat.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=flat_elev)
        )
        t += 30.0

    # Large active bookend after: 6 points, +20m per step → 100m change.
    after: list[TrackPoint] = []
    after_start = flat_elev + 10.0
    for i in range(6):
        after.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=after_start + i * 20.0)
        )
        t += 10.0

    pts = tuple(tiny_before + flat + after)
    seg = Segment(segment_type=SegmentType.ASCENT, points=pts)

    result = _split_interior_gaps(
        seg, time_window=60.0, flatness_threshold=3.0,
        min_trim_duration=120.0, min_height=10.0,
    )

    # The tiny bookend (4m change) should be discarded; only the large one survives.
    for sub in result:
        delta = abs(sub.end_elevation - sub.start_elevation)
        assert delta >= 10.0, f"Sub-segment with |Δelev|={delta} should have been discarded"


def test_split_discards_contradictory_classification() -> None:
    """A sub-segment whose elevation direction contradicts its classification is discarded.

    Build an ASCENT segment where, after splitting at an interior flat,
    one sub-segment actually descends. That sub-segment should be discarded.
    Requirements: 2.3, 6.4, 6.5
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t = 0.0

    # Descending bookend (contradicts ASCENT): 6 points, -20m per step.
    descending: list[TrackPoint] = []
    for i in range(6):
        descending.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=300.0 - i * 20.0)
        )
        t += 10.0

    # Interior flat: 8 points, 30s apart.
    flat: list[TrackPoint] = []
    flat_elev = descending[-1].elevation - 10.0
    for i in range(8):
        flat.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=flat_elev)
        )
        t += 30.0

    # Ascending bookend (matches ASCENT): 6 points, +20m per step.
    ascending: list[TrackPoint] = []
    asc_start = flat_elev + 10.0
    for i in range(6):
        ascending.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=asc_start + i * 20.0)
        )
        t += 10.0

    pts = tuple(descending + flat + ascending)
    seg = Segment(segment_type=SegmentType.ASCENT, points=pts)

    result = _split_interior_gaps(
        seg, time_window=60.0, flatness_threshold=3.0,
        min_trim_duration=120.0, min_height=10.0,
    )

    # The descending sub-segment contradicts ASCENT and should be discarded.
    for sub in result:
        delta = sub.end_elevation - sub.start_elevation
        assert delta > 0, (
            f"ASCENT sub-segment has descending elevation (Δ={delta}), "
            "should have been discarded"
        )


# ---------------------------------------------------------------------------
# 8.3 — Merge and edge cases
# ---------------------------------------------------------------------------


def test_merge_after_trim() -> None:
    """Adjacent same-direction segments after trimming are merged.

    Build two ASCENT segments separated by a short DESCENT segment.
    After the full trim pipeline discards the DESCENT (too small), the
    two ASCENTs become adjacent and should be merged.
    Requirements: 7.1
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t = 0.0

    # ASCENT 1: 100 → 200 over 5 points, 30s apart.
    asc1_pts: list[TrackPoint] = []
    for i in range(5):
        asc1_pts.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=100.0 + i * 25.0)
        )
        t += 30.0

    # Small DESCENT: 200 → 195 over 3 points (Δ=5, below min_height=10).
    desc_pts: list[TrackPoint] = []
    for i in range(3):
        desc_pts.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=200.0 - i * 2.5)
        )
        t += 30.0

    # ASCENT 2: 195 → 295 over 5 points.
    asc2_pts: list[TrackPoint] = []
    for i in range(5):
        asc2_pts.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=195.0 + i * 25.0)
        )
        t += 30.0

    all_points = asc1_pts + desc_pts + asc2_pts

    seg1 = Segment(segment_type=SegmentType.ASCENT, points=tuple(asc1_pts))
    seg2 = Segment(segment_type=SegmentType.ASCENT, points=tuple(asc2_pts))

    merged = _merge_adjacent_same_direction([seg1, seg2], all_points)

    assert len(merged) == 1
    assert merged[0].segment_type == SegmentType.ASCENT
    # Merged segment should span from first point of seg1 to last point of seg2,
    # including all intermediate points.
    assert merged[0].points[0] is asc1_pts[0]
    assert merged[0].points[-1] is asc2_pts[-1]
    assert len(merged[0].points) == len(all_points)


def test_non_uniform_timestamps() -> None:
    """Flat detection uses timestamps, not index count.

    Build a segment where the first 3 points are closely spaced (1s apart,
    total 2s) and flat, but don't meet min_trim_duration=120s. Then add
    widely-spaced non-flat points. The flat region should NOT be trimmed
    because its duration is too short.
    Requirements: 3.5
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # 3 flat points, 1s apart → 2s total duration (way below 120s).
    flat = [
        TrackPoint(timestamp=base + timedelta(seconds=0), elevation=100.0),
        TrackPoint(timestamp=base + timedelta(seconds=1), elevation=100.5),
        TrackPoint(timestamp=base + timedelta(seconds=2), elevation=100.0),
    ]
    # Active points, widely spaced.
    active = [
        TrackPoint(timestamp=base + timedelta(seconds=60), elevation=120.0),
        TrackPoint(timestamp=base + timedelta(seconds=120), elevation=150.0),
        TrackPoint(timestamp=base + timedelta(seconds=180), elevation=180.0),
    ]
    pts = tuple(flat + active)
    seg = Segment(segment_type=SegmentType.ASCENT, points=pts)

    result = _trim_boundaries(seg, time_window=60.0, flatness_threshold=3.0, min_trim_duration=120.0)

    assert result is not None
    # The flat region is only 2s, so it should NOT be trimmed.
    assert result.points == pts


def test_short_flat_below_min_duration() -> None:
    """A flat stretch shorter than min_trim_duration is NOT trimmed.

    Build a segment with a leading flat stretch of 60s (below min_trim_duration=120s).
    Requirements: 4.3
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Leading flat: 4 points, 20s apart → 60s total.
    flat = [
        TrackPoint(timestamp=base + timedelta(seconds=i * 20), elevation=100.0)
        for i in range(4)
    ]
    # Active ascent.
    active = [
        TrackPoint(timestamp=base + timedelta(seconds=80 + i * 30), elevation=130.0 + i * 20.0)
        for i in range(5)
    ]
    pts = tuple(flat + active)
    seg = Segment(segment_type=SegmentType.ASCENT, points=pts)

    result = _trim_boundaries(seg, time_window=60.0, flatness_threshold=3.0, min_trim_duration=120.0)

    assert result is not None
    # The 60s flat stretch is below min_trim_duration=120s, so no trimming.
    assert result.points == pts


def test_flat_exactly_at_threshold() -> None:
    """Elevation range exactly equal to flatness_threshold is classified as flat.

    Requirements: 3.2
    """
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # 3 points: min=100, max=103 → range = 3.0 = flatness_threshold.
    pts = [
        TrackPoint(timestamp=base + timedelta(seconds=0), elevation=100.0),
        TrackPoint(timestamp=base + timedelta(seconds=30), elevation=103.0),
        TrackPoint(timestamp=base + timedelta(seconds=60), elevation=101.0),
    ]

    assert _is_window_flat(pts, 0, 2, flatness_threshold=3.0) is True

    # Range of 3.01 should NOT be flat.
    pts_over = [
        TrackPoint(timestamp=base + timedelta(seconds=0), elevation=100.0),
        TrackPoint(timestamp=base + timedelta(seconds=30), elevation=103.01),
        TrackPoint(timestamp=base + timedelta(seconds=60), elevation=101.0),
    ]

    assert _is_window_flat(pts_over, 0, 2, flatness_threshold=3.0) is False
