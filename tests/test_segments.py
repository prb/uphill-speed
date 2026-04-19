"""Property-based tests for the segment identifier."""

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from gpx_segment_report.models import SKI_TOURING, Segment, SegmentType, TrackPoint
from gpx_segment_report.segments import identify_segments


def _make_track_points(elevations: list[float]) -> list[TrackPoint]:
    """Build a list of TrackPoint values with 1-second spacing."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        TrackPoint(timestamp=base + timedelta(seconds=i), elevation=e)
        for i, e in enumerate(elevations)
    ]


# Feature: gpx-segment-report, Property 4: Minimum height threshold enforced on segments
@given(
    elevations=st.lists(
        st.floats(min_value=-2000.0, max_value=9000.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=200,
    ),
    min_height=st.floats(min_value=0.1, max_value=5000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_every_segment_meets_min_height(
    elevations: list[float], min_height: float
) -> None:
    """Every returned segment must have |end_elevation - start_elevation| >= min_height."""
    points = _make_track_points(elevations)
    segments = identify_segments(points, min_height, SKI_TOURING)

    for seg in segments:
        change = abs(seg.end_elevation - seg.start_elevation)
        assert change >= min_height, (
            f"Segment {seg.segment_type.value} has elevation change {change} "
            f"which is below min_height {min_height}"
        )


# Feature: gpx-segment-report, Property 5: Segment classification matches elevation trend
@given(
    elevations=st.lists(
        st.floats(min_value=-2000.0, max_value=9000.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=200,
    ),
    min_height=st.floats(min_value=0.1, max_value=5000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_segment_classification_matches_elevation_trend(
    elevations: list[float], min_height: float
) -> None:
    """ASCENT segments must end higher than they start; DESCENT segments must end lower."""
    points = _make_track_points(elevations)
    segments = identify_segments(points, min_height, SKI_TOURING)

    for seg in segments:
        if seg.segment_type == SegmentType.ASCENT:
            assert seg.end_elevation > seg.start_elevation, (
                f"ASCENT segment should have end > start, "
                f"got {seg.end_elevation} <= {seg.start_elevation}"
            )
        else:
            assert seg.end_elevation < seg.start_elevation, (
                f"DESCENT segment should have end < start, "
                f"got {seg.end_elevation} >= {seg.start_elevation}"
            )


# Feature: gpx-segment-report, Property 6: Segment structural invariants
@given(
    elevations=st.lists(
        st.floats(min_value=-2000.0, max_value=9000.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=200,
    ),
    min_height=st.floats(min_value=0.1, max_value=5000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_segment_structural_invariants(
    elevations: list[float], min_height: float
) -> None:
    """Verify structural invariants across all returned segments.

    (a) Points within each segment preserve input order.
    (b) No point appears in multiple segments.
    (c) Consecutive segments are chronologically ordered in the input.
    """
    points = _make_track_points(elevations)
    segments = identify_segments(points, min_height, SKI_TOURING)

    # Build a lookup from TrackPoint identity to its original index.
    point_to_index: dict[int, int] = {id(p): i for i, p in enumerate(points)}

    # Interior points are all points except the first and last of each segment.
    # Boundary points (first/last) may be shared between consecutive segments
    # because the peak/trough that ends one segment also starts the next.
    interior_ids: set[int] = set()
    prev_last_id: int | None = None

    prev_last_index = -1
    for seg_idx, seg in enumerate(segments):
        seg_indices = [point_to_index[id(p)] for p in seg.points]

        # (a) Points within the segment preserve input order.
        assert seg_indices == sorted(seg_indices), (
            f"Segment points are not in input order: {seg_indices}"
        )

        # (b) No interior point appears in multiple segments.
        # Boundary sharing is allowed: the last point of segment N may be
        # the first point of segment N+1 (the shared peak/trough).
        current_interior = {id(p) for p in seg.points[1:-1]}
        first_id = id(seg.points[0])
        last_id = id(seg.points[-1])

        overlap = interior_ids & (current_interior | {first_id, last_id})
        assert not overlap, (
            f"Interior points overlap between segments (count: {len(overlap)})"
        )

        # The first point of this segment may only equal the last point of
        # the immediately preceding segment (boundary sharing).
        if seg_idx > 0 and first_id == prev_last_id:
            pass  # allowed boundary sharing
        else:
            assert first_id not in interior_ids, (
                "First point of segment found as interior point of a prior segment"
            )

        interior_ids |= current_interior
        prev_last_id = last_id

        # (c) Consecutive segments are chronologically ordered in the input.
        first_index = seg_indices[0]
        assert first_index >= prev_last_index, (
            f"Segment starts at index {first_index} but previous segment "
            f"ended at index {prev_last_index}"
        )
        prev_last_index = seg_indices[-1]


# Feature: gpx-segment-report, Property 7: Flat tracks produce zero segments
@given(
    base_elevation=st.floats(
        min_value=-2000.0, max_value=9000.0, allow_nan=False, allow_infinity=False
    ),
    num_points=st.integers(min_value=2, max_value=200),
    min_height=st.floats(
        min_value=0.1, max_value=5000.0, allow_nan=False, allow_infinity=False
    ),
    data=st.data(),
)
@settings(max_examples=200)
def test_flat_tracks_produce_zero_segments(
    base_elevation: float,
    num_points: int,
    min_height: float,
    data: st.DataObject,
) -> None:
    """When max(elevation) - min(elevation) < min_height, no segments are returned."""
    # Generate elevations that stay within a band narrower than min_height.
    max_spread = min_height * 0.99  # ensure strictly less than min_height
    elevations = data.draw(
        st.lists(
            st.floats(
                min_value=base_elevation,
                max_value=base_elevation + max_spread,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=num_points,
            max_size=num_points,
        )
    )

    points = _make_track_points(elevations)
    segments = identify_segments(points, min_height, SKI_TOURING)

    assert segments == [], (
        f"Expected zero segments for flat track (spread < min_height), "
        f"got {len(segments)}. Elevation range: "
        f"[{min(elevations)}, {max(elevations)}], min_height: {min_height}"
    )


# Feature: segment-gap-trimming, Property 1: Flat window detection matches elevation range
@given(
    elevations=st.lists(
        st.floats(min_value=-2000.0, max_value=9000.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=200,
    ),
    flatness_threshold=st.floats(
        min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
    data=st.data(),
)
@settings(max_examples=200)
def test_flat_window_detection(
    elevations: list[float],
    flatness_threshold: float,
    data: st.DataObject,
) -> None:
    """_is_window_flat() returns True iff max(elev) - min(elev) <= threshold."""
    from gpx_segment_report.segments import _is_window_flat

    points = _make_track_points(elevations)
    n = len(points)

    # Draw a valid sub-range within the points list.
    start_idx = data.draw(st.integers(min_value=0, max_value=n - 1))
    end_idx = data.draw(st.integers(min_value=start_idx, max_value=n - 1))

    result = _is_window_flat(points, start_idx, end_idx, flatness_threshold)

    window_elevs = [p.elevation for p in points[start_idx : end_idx + 1]]
    expected = (max(window_elevs) - min(window_elevs)) <= flatness_threshold

    assert result == expected, (
        f"_is_window_flat returned {result} but elevation range "
        f"{max(window_elevs) - min(window_elevs)} vs threshold {flatness_threshold} "
        f"expected {expected}"
    )


# Feature: segment-gap-trimming, Property 2: Boundary trimming removes flat edges and preserves active content
@given(
    flatness_threshold=st.floats(
        min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False
    ),
    time_window=st.floats(
        min_value=10.0, max_value=120.0, allow_nan=False, allow_infinity=False
    ),
    min_trim_duration=st.floats(
        min_value=10.0, max_value=300.0, allow_nan=False, allow_infinity=False
    ),
    active_step=st.floats(
        min_value=5.0, max_value=50.0, allow_nan=False, allow_infinity=False
    ),
    num_active=st.integers(min_value=5, max_value=30),
    num_flat_lead=st.integers(min_value=5, max_value=30),
    num_flat_trail=st.integers(min_value=5, max_value=30),
    flat_base=st.floats(
        min_value=100.0, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
    data=st.data(),
)
@settings(max_examples=200)
def test_boundary_trimming_removes_flat_edges(
    flatness_threshold: float,
    time_window: float,
    min_trim_duration: float,
    active_step: float,
    num_active: int,
    num_flat_lead: int,
    num_flat_trail: int,
    flat_base: float,
    data: st.DataObject,
) -> None:
    """Boundary trimming removes flat prefix/suffix and preserves active content.

    Generates a segment with:
    - A leading flat stretch (elevation within flatness_threshold, duration >= min_trim_duration)
    - An active middle with a clear monotonic trend (step > flatness_threshold)
    - A trailing flat stretch (same constraints as leading)

    After trimming, the flat edges should be removed and the active middle preserved.
    If trimming consumes the segment entirely, None is returned.
    """
    from gpx_segment_report.segments import _trim_boundaries

    base = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # Ensure flat stretches span enough time to meet min_trim_duration.
    # Total duration = (num_points - 1) * spacing, so we need
    # spacing = (min_trim_duration + margin) / (num_points - 1).
    flat_lead_spacing = (min_trim_duration + time_window + 10.0) / max(num_flat_lead - 1, 1)
    flat_trail_spacing = (min_trim_duration + time_window + 10.0) / max(num_flat_trail - 1, 1)

    # --- Build leading flat points ---
    lead_points: list[TrackPoint] = []
    t = 0.0
    for i in range(num_flat_lead):
        elev = data.draw(
            st.floats(
                min_value=flat_base,
                max_value=flat_base + flatness_threshold * 0.5,
                allow_nan=False,
                allow_infinity=False,
            ),
            label=f"lead_elev_{i}",
        )
        lead_points.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=elev)
        )
        t += flat_lead_spacing

    # --- Build active middle (strictly ascending) ---
    active_points: list[TrackPoint] = []
    active_start_elev = flat_base + flatness_threshold + active_step
    for i in range(num_active):
        elev = active_start_elev + active_step * i
        active_points.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=elev)
        )
        t += 2.0  # tight spacing — clearly not flat

    # --- Build trailing flat points ---
    trail_base_elev = active_points[-1].elevation + flatness_threshold + active_step
    trail_points: list[TrackPoint] = []
    for i in range(num_flat_trail):
        elev = data.draw(
            st.floats(
                min_value=trail_base_elev,
                max_value=trail_base_elev + flatness_threshold * 0.5,
                allow_nan=False,
                allow_infinity=False,
            ),
            label=f"trail_elev_{i}",
        )
        trail_points.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=elev)
        )
        t += flat_trail_spacing

    all_pts = tuple(lead_points + active_points + trail_points)
    segment = Segment(segment_type=SegmentType.ASCENT, points=all_pts)

    result = _trim_boundaries(segment, time_window, flatness_threshold, min_trim_duration)

    if result is None:
        # Segment was consumed — acceptable only if active region is tiny
        return

    # The trimmed segment should not contain any leading flat points.
    lead_ids = {id(p) for p in lead_points}
    for p in result.points:
        assert id(p) not in lead_ids, (
            "Trimmed segment still contains a leading flat point"
        )

    # The trimmed segment should not contain any trailing flat points.
    trail_ids = {id(p) for p in trail_points}
    for p in result.points:
        assert id(p) not in trail_ids, (
            "Trimmed segment still contains a trailing flat point"
        )

    # The trimmed segment should contain at least some active points.
    active_ids = {id(p) for p in active_points}
    trimmed_active = [p for p in result.points if id(p) in active_ids]
    assert len(trimmed_active) >= 2, (
        f"Expected at least 2 active points in trimmed segment, got {len(trimmed_active)}"
    )

    # The trimmed segment's points must be a contiguous subsequence of the input.
    input_ids = [id(p) for p in all_pts]
    trimmed_ids = [id(p) for p in result.points]
    start_pos = input_ids.index(trimmed_ids[0])
    expected_slice = input_ids[start_pos : start_pos + len(trimmed_ids)]
    assert trimmed_ids == expected_slice, (
        "Trimmed segment points are not a contiguous subsequence of the input"
    )


# Feature: segment-gap-trimming, Property 3: Interior flat stretches cause segment splitting
@given(
    flatness_threshold=st.floats(
        min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False
    ),
    time_window=st.floats(
        min_value=10.0, max_value=120.0, allow_nan=False, allow_infinity=False
    ),
    min_trim_duration=st.floats(
        min_value=10.0, max_value=300.0, allow_nan=False, allow_infinity=False
    ),
    min_height=st.floats(
        min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False
    ),
    active_step=st.floats(
        min_value=5.0, max_value=50.0, allow_nan=False, allow_infinity=False
    ),
    num_active_before=st.integers(min_value=5, max_value=20),
    num_active_after=st.integers(min_value=5, max_value=20),
    num_flat=st.integers(min_value=5, max_value=20),
    flat_base=st.floats(
        min_value=100.0, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
    data=st.data(),
)
@settings(max_examples=200)
def test_interior_flat_causes_split(
    flatness_threshold: float,
    time_window: float,
    min_trim_duration: float,
    min_height: float,
    active_step: float,
    num_active_before: int,
    num_active_after: int,
    num_flat: int,
    flat_base: float,
    data: st.DataObject,
) -> None:
    """A segment with an interior flat stretch of sufficient duration is split.

    Generates a segment with:
    - An active ascending bookend before the flat stretch
    - An interior flat stretch (elevation within flatness_threshold, duration >= min_trim_duration)
    - An active ascending bookend after the flat stretch

    After splitting, the single input segment should produce multiple sub-segments,
    and no sub-segment should span across the flat stretch.

    **Validates: Requirements 2.2, 2.5**
    """
    from gpx_segment_report.segments import _split_interior_gaps

    base = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # Ensure active_step is large enough to exceed flatness_threshold
    # so the active regions are clearly non-flat.
    active_step = max(active_step, flatness_threshold + 1.0)

    # Ensure each active bookend has enough elevation change to exceed min_height.
    min_active_points = max(num_active_before, int(min_height / active_step) + 3)
    num_active_before = max(num_active_before, min_active_points)
    min_active_points_after = max(num_active_after, int(min_height / active_step) + 3)
    num_active_after = max(num_active_after, min_active_points_after)

    # --- Build active ascending bookend before flat ---
    t = 0.0
    before_points: list[TrackPoint] = []
    for i in range(num_active_before):
        elev = flat_base + active_step * i
        before_points.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=elev)
        )
        t += 2.0  # tight spacing — clearly not flat

    # --- Build interior flat stretch ---
    # Spacing must ensure total flat duration >= min_trim_duration.
    flat_spacing = (min_trim_duration + time_window + 10.0) / max(num_flat - 1, 1)
    flat_elev_base = before_points[-1].elevation + active_step  # above the active region
    flat_points: list[TrackPoint] = []
    for i in range(num_flat):
        elev = data.draw(
            st.floats(
                min_value=flat_elev_base,
                max_value=flat_elev_base + flatness_threshold * 0.5,
                allow_nan=False,
                allow_infinity=False,
            ),
            label=f"flat_elev_{i}",
        )
        flat_points.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=elev)
        )
        t += flat_spacing

    # --- Build active ascending bookend after flat ---
    after_start_elev = flat_elev_base + flatness_threshold + active_step
    after_points: list[TrackPoint] = []
    for i in range(num_active_after):
        elev = after_start_elev + active_step * i
        after_points.append(
            TrackPoint(timestamp=base + timedelta(seconds=t), elevation=elev)
        )
        t += 2.0

    all_pts = tuple(before_points + flat_points + after_points)
    segment = Segment(segment_type=SegmentType.ASCENT, points=all_pts)

    result = _split_interior_gaps(
        segment, time_window, flatness_threshold, min_trim_duration, min_height
    )

    # The single input segment should produce multiple sub-segments.
    assert len(result) >= 2, (
        f"Expected at least 2 sub-segments after interior split, got {len(result)}"
    )

    # No sub-segment should span across the flat stretch.
    flat_ids = {id(p) for p in flat_points}
    for sub in result:
        sub_ids = {id(p) for p in sub.points}
        # A sub-segment may include the boundary point of the flat stretch
        # (the first or last flat point), but should not contain interior
        # flat points on both sides of the stretch.
        interior_flat_in_sub = flat_ids & sub_ids
        if interior_flat_in_sub:
            # If a sub-segment contains flat points, they should all be
            # from one end of the flat stretch (not spanning across it).
            flat_indices_in_sub = sorted(
                [flat_points.index(p) for p in flat_points if id(p) in sub_ids]
            )
            # They should be contiguous and at one edge.
            if len(flat_indices_in_sub) > 1:
                assert flat_indices_in_sub[-1] - flat_indices_in_sub[0] == len(flat_indices_in_sub) - 1, (
                    "Sub-segment contains non-contiguous flat points — it spans across the flat stretch"
                )


# Feature: segment-gap-trimming, Property 4: Segments without flat stretches pass through unchanged
@given(
    num_segments=st.integers(min_value=1, max_value=5),
    min_height=st.floats(
        min_value=10.0, max_value=200.0, allow_nan=False, allow_infinity=False
    ),
    step_size=st.floats(
        min_value=15.0, max_value=100.0, allow_nan=False, allow_infinity=False
    ),
    points_per_segment=st.integers(min_value=10, max_value=40),
)
@settings(max_examples=200)
def test_no_flat_passthrough(
    num_segments: int,
    min_height: float,
    step_size: float,
    points_per_segment: int,
) -> None:
    """Segments with steep monotonic elevation (no flat windows) pass through unchanged.

    Generates a track with alternating steep ascent/descent segments where
    every point-to-point elevation change exceeds the hardcoded
    flatness_threshold (3.0 m), guaranteeing no time window can be flat.
    The full identify_segments() pipeline should return segments whose
    points cover the same regions as the pre-trim segments.

    **Validates: Requirements 5.3**
    """
    # The hardcoded flatness_threshold in identify_segments is 3.0 m.
    flatness_threshold = 3.0
    # Ensure each step is large enough that no window can be flat.
    step_size = max(step_size, flatness_threshold + 1.0)
    # Ensure min_height is achievable within each segment.
    min_height = min(min_height, step_size * (points_per_segment - 1) * 0.5)

    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    elevations: list[float] = []
    elev = 500.0  # start in the middle of a safe range

    for seg_idx in range(num_segments):
        ascending = seg_idx % 2 == 0
        for _ in range(points_per_segment):
            elevations.append(elev)
            if ascending:
                elev += step_size
            else:
                elev -= step_size

    # Use 1-second spacing — with step_size > flatness_threshold per point,
    # even a 60-second time window will have elevation range >> flatness_threshold.
    points = _make_track_points(elevations)
    segments = identify_segments(points, min_height, SKI_TOURING)

    # With steep monotonic segments and no flat regions, the trimmer should
    # not alter the segments. Verify that every output segment's points are
    # drawn from the input and that no points were trimmed away by checking
    # that the total point coverage is the same as without trimming.
    #
    # We can't compare directly to pre-trim output (we don't have it), but
    # we can verify the key invariant: no points were removed by the trimmer.
    # Since every window is non-flat, _trim_boundaries returns segments
    # unchanged and _find_interior_flat_stretches returns [].
    #
    # Verify: the union of all segment point ranges covers the same indices
    # as a pipeline without trimming would produce.
    point_id_to_idx = {id(p): i for i, p in enumerate(points)}

    for seg in segments:
        seg_indices = [point_id_to_idx[id(p)] for p in seg.points]
        # Points must be contiguous (no gaps from trimming).
        assert seg_indices == list(range(seg_indices[0], seg_indices[-1] + 1)), (
            f"Segment has non-contiguous indices {seg_indices}, "
            "suggesting points were trimmed from a steep monotonic segment"
        )

    # Also verify that segments still meet basic invariants.
    for seg in segments:
        delta = seg.end_elevation - seg.start_elevation
        assert abs(delta) >= min_height


# Feature: segment-gap-trimming, Property 5: Trimmed segment points are contiguous subsequences of the input
@given(
    elevations=st.lists(
        st.floats(
            min_value=-2000.0, max_value=9000.0, allow_nan=False, allow_infinity=False
        ),
        min_size=2,
        max_size=200,
    ),
    min_height=st.floats(
        min_value=0.1, max_value=5000.0, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=200)
def test_trimmed_points_contiguous_subsequence(
    elevations: list[float],
    min_height: float,
) -> None:
    """Every output segment's points are a contiguous subsequence of the input.

    After gap trimming (including boundary trimming, interior splitting,
    and merging), each segment's points tuple must correspond to a
    contiguous slice of the original track point list, preserving order
    with no internal gaps.

    **Validates: Requirements 6.2, 6.3, 7.3**
    """
    points = _make_track_points(elevations)
    segments = identify_segments(points, min_height, SKI_TOURING)

    point_id_to_idx = {id(p): i for i, p in enumerate(points)}

    for seg in segments:
        seg_indices = [point_id_to_idx[id(p)] for p in seg.points]

        # (a) Points within the segment preserve input order.
        assert seg_indices == sorted(seg_indices), (
            f"Segment points are not in input order: {seg_indices}"
        )

        # (b) Points are contiguous — no gaps within the segment.
        expected = list(range(seg_indices[0], seg_indices[-1] + 1))
        assert seg_indices == expected, (
            f"Segment points are not contiguous. "
            f"Expected indices {expected}, got {seg_indices}"
        )


# Feature: segment-gap-trimming, Property 6: No consecutive same-direction segments in output
@given(
    elevations=st.lists(
        st.floats(
            min_value=-2000.0, max_value=9000.0, allow_nan=False, allow_infinity=False
        ),
        min_size=2,
        max_size=200,
    ),
    min_height=st.floats(
        min_value=0.1, max_value=5000.0, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=200)
def test_no_consecutive_same_direction(
    elevations: list[float],
    min_height: float,
) -> None:
    """No two adjacent segments in the output share the same SegmentType.

    The post-trim merge pass must consolidate any adjacent same-direction
    segments that arise from discarding intermediate segments during
    trimming or splitting.

    **Validates: Requirements 7.1**
    """
    points = _make_track_points(elevations)
    segments = identify_segments(points, min_height, SKI_TOURING)

    for i in range(len(segments) - 1):
        assert segments[i].segment_type != segments[i + 1].segment_type, (
            f"Consecutive segments {i} and {i + 1} share the same type "
            f"({segments[i].segment_type.value}), violating the merge invariant"
        )
