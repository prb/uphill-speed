"""Segment identification using Ramer-Douglas-Peucker simplification.

Simplifies the elevation-vs-index profile with the RDP algorithm, then
classifies, filters, and merges the resulting boundary pairs into
coarse-grained ascending/descending segments.
"""

import math

from gpx_segment_report.models import Segment, SegmentType, SportProfile, TrackPoint


def _perpendicular_distance(
    point: tuple[float, float],
    line_start: tuple[float, float],
    line_end: tuple[float, float],
) -> float:
    """Perpendicular distance from *point* to the line through *line_start* and *line_end*.

    Uses the standard cross-product formula. When *line_start* equals
    *line_end* (degenerate line), returns the Euclidean distance from
    *point* to *line_start*.
    """
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end

    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)

    if length == 0.0:
        return math.hypot(x0 - x1, y0 - y1)

    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / length


def _rdp_simplify(
    points: list[tuple[float, float]],
    epsilon: float,
) -> list[int]:
    """Simplify a polyline using the Ramer-Douglas-Peucker algorithm.

    Operates on a list of ``(x, y)`` tuples and returns a **sorted** list
    of indices into *points* that form the simplified polyline.

    Args:
        points: Ordered 2-D points describing the polyline.
        epsilon: Perpendicular-distance tolerance.  Points closer than
            this to the line between endpoints are discarded.

    Returns:
        Sorted indices of the retained points.
    """
    n = len(points)
    if n <= 2:
        return list(range(n))

    # Find the point with the maximum perpendicular distance from the
    # line connecting the first and last points.
    start = points[0]
    end = points[-1]
    max_dist = 0.0
    max_idx = 0
    for i in range(1, n - 1):
        d = _perpendicular_distance(points[i], start, end)
        if d > max_dist:
            max_dist = d
            max_idx = i

    if max_dist >= epsilon:
        # Recurse on both halves and merge, removing the duplicate split point.
        left = _rdp_simplify(points[: max_idx + 1], epsilon)
        right = _rdp_simplify(points[max_idx:], epsilon)
        # Translate right-half local indices to global indices.
        return left + [idx + max_idx for idx in right[1:]]
    else:
        return [0, n - 1]


def _is_window_flat(
    points: tuple[TrackPoint, ...] | list[TrackPoint],
    start_idx: int,
    end_idx: int,
    flatness_threshold: float,
) -> bool:
    """Check whether the elevation range within a slice of points is flat.

    Computes ``max(elevation) - min(elevation)`` over
    ``points[start_idx:end_idx+1]`` and returns ``True`` when the range
    is at or below *flatness_threshold*.
    """
    elevations = [p.elevation for p in points[start_idx : end_idx + 1]]
    return max(elevations) - min(elevations) <= flatness_threshold


def _find_leading_flat(
    points: tuple[TrackPoint, ...],
    time_window: float,
    flatness_threshold: float,
) -> int:
    """Return the index of the first point after the leading flat stretch.

    Scans forward from index 0 using time-based windows of duration
    *time_window* seconds.  Extends as long as consecutive windows remain
    flat (elevation range ≤ *flatness_threshold*).

    Returns 0 if no leading flat stretch is detected.
    Returns ``len(points)`` if the entire sequence is flat.
    """
    n = len(points)
    if n < 2:
        return 0

    # Check the first full time window anchored at index 0.
    t_start = points[0].timestamp
    win_end = 0
    for j in range(n):
        if (points[j].timestamp - t_start).total_seconds() <= time_window:
            win_end = j
        else:
            break

    if not _is_window_flat(points, 0, win_end, flatness_threshold):
        return 0  # no leading flat

    # The first window is flat.  Extend point-by-point as long as each
    # new point keeps the trailing time_window-sized window flat.
    flat_end = win_end  # inclusive index of the last confirmed flat point
    for j in range(win_end + 1, n):
        # Find the start of the window ending at j.
        t_j = points[j].timestamp
        ws = j
        for k in range(j, -1, -1):
            if (t_j - points[k].timestamp).total_seconds() <= time_window:
                ws = k
            else:
                break
        if _is_window_flat(points, ws, j, flatness_threshold):
            flat_end = j
        else:
            break

    return flat_end + 1


def _find_trailing_flat(
    points: tuple[TrackPoint, ...],
    time_window: float,
    flatness_threshold: float,
) -> int:
    """Return the index one past the last point before the trailing flat stretch.

    Scans backward from the last point using time-based windows of
    duration *time_window* seconds.  Extends as long as consecutive
    windows remain flat.

    Returns ``len(points)`` if no trailing flat stretch is detected.
    Returns 0 if the entire sequence is flat.
    """
    n = len(points)
    if n < 2:
        return n

    # Check the last full time window anchored at the final point.
    t_end = points[-1].timestamp
    win_start = n - 1
    for j in range(n - 1, -1, -1):
        if (t_end - points[j].timestamp).total_seconds() <= time_window:
            win_start = j
        else:
            break

    if not _is_window_flat(points, win_start, n - 1, flatness_threshold):
        return n  # no trailing flat

    # The last window is flat.  Extend point-by-point backward as long as
    # each new point keeps the leading time_window-sized window flat.
    flat_start = win_start  # inclusive index of the earliest confirmed flat point
    for j in range(win_start - 1, -1, -1):
        # Find the end of the window starting at j.
        t_j = points[j].timestamp
        we = j
        for k in range(j, n):
            if (points[k].timestamp - t_j).total_seconds() <= time_window:
                we = k
            else:
                break
        if _is_window_flat(points, j, we, flatness_threshold):
            flat_start = j
        else:
            break

    return flat_start


def _trim_boundaries(
    segment: Segment,
    time_window: float,
    flatness_threshold: float,
    min_trim_duration: float,
) -> Segment | None:
    """Trim leading and trailing flat stretches from a segment.

    Only trims a flat stretch if its duration is ≥ *min_trim_duration*
    seconds.  Returns ``None`` if trimming leaves fewer than 2 points.
    """
    pts = segment.points

    # --- leading flat ---
    lead_idx = _find_leading_flat(pts, time_window, flatness_threshold)
    if lead_idx > 0:
        lead_duration = (
            pts[lead_idx - 1].timestamp - pts[0].timestamp
        ).total_seconds()
        if lead_duration < min_trim_duration:
            lead_idx = 0  # don't trim — too short

    # --- trailing flat ---
    trail_idx = _find_trailing_flat(pts, time_window, flatness_threshold)
    if trail_idx < len(pts):
        trail_duration = (
            pts[-1].timestamp - pts[trail_idx].timestamp
        ).total_seconds()
        if trail_duration < min_trim_duration:
            trail_idx = len(pts)  # don't trim — too short

    trimmed = pts[lead_idx:trail_idx]
    if len(trimmed) < 2:
        return None

    return Segment(segment_type=segment.segment_type, points=tuple(trimmed))


def _find_interior_flat_stretches(
    points: tuple[TrackPoint, ...],
    time_window: float,
    flatness_threshold: float,
    min_trim_duration: float,
) -> list[tuple[int, int]]:
    """Find all interior flat stretches meeting the minimum trim duration.

    Returns a list of (start_idx, end_idx) tuples (inclusive) marking
    flat regions. Only stretches fully interior to the segment (not
    touching the first or last point) are returned, since boundary
    trimming handles edges.
    """
    n = len(points)
    if n < 3:
        return []  # need at least 3 points to have an interior

    stretches: list[tuple[int, int]] = []
    i = 1  # start from index 1 (skip first point — boundary trimming handles it)

    while i < n - 1:  # stop before last point
        # Find the end of the time window starting at i.
        win_end = i
        t_i = points[i].timestamp
        for j in range(i, n):
            if (points[j].timestamp - t_i).total_seconds() <= time_window:
                win_end = j
            else:
                break

        if not _is_window_flat(points, i, win_end, flatness_threshold):
            i += 1
            continue

        # The window starting at i is flat. Extend the flat stretch forward
        # point-by-point as long as each new point keeps the trailing
        # time_window-sized window flat.
        flat_start = i
        flat_end = win_end
        for j in range(win_end + 1, n):
            # Find the start of the window ending at j.
            t_j = points[j].timestamp
            ws = j
            for k in range(j, -1, -1):
                if (t_j - points[k].timestamp).total_seconds() <= time_window:
                    ws = k
                else:
                    break
            if _is_window_flat(points, ws, j, flatness_threshold):
                flat_end = j
            else:
                break

        # Check duration of the flat stretch.
        duration = (
            points[flat_end].timestamp - points[flat_start].timestamp
        ).total_seconds()

        # Only record if fully interior (not touching first or last point)
        # and meets minimum trim duration.
        if (
            flat_start > 0
            and flat_end < n - 1
            and duration >= min_trim_duration
        ):
            stretches.append((flat_start, flat_end))

        # Advance past this flat stretch.
        i = flat_end + 1

    return stretches


def _split_interior_gaps(
    segment: Segment,
    time_window: float,
    flatness_threshold: float,
    min_trim_duration: float,
    min_height: float,
) -> list[Segment]:
    """Split a segment at interior flat stretches.

    Each resulting sub-segment inherits the original segment's classification.
    Sub-segments with |Δelev| < min_height are discarded.
    Sub-segments whose classification contradicts their elevation direction
    are discarded.
    """
    pts = segment.points
    flat_stretches = _find_interior_flat_stretches(
        pts, time_window, flatness_threshold, min_trim_duration
    )

    if not flat_stretches:
        return [segment]

    # Build sub-segments from the active regions between flat stretches.
    sub_segments: list[Segment] = []
    prev_end = 0  # start of the next active region

    for flat_start, flat_end in flat_stretches:
        # Active region is from prev_end to flat_start (inclusive).
        if flat_start > prev_end:
            active_pts = pts[prev_end : flat_start + 1]
            if len(active_pts) >= 2:
                sub_segments.append(
                    Segment(
                        segment_type=segment.segment_type,
                        points=tuple(active_pts),
                    )
                )
        prev_end = flat_end  # next active region starts at flat_end

    # Trailing active region after the last flat stretch.
    if prev_end < len(pts):
        active_pts = pts[prev_end : len(pts)]
        if len(active_pts) >= 2:
            sub_segments.append(
                Segment(
                    segment_type=segment.segment_type,
                    points=tuple(active_pts),
                )
            )

    # Filter: discard sub-segments with |Δelev| < min_height.
    # Filter: discard sub-segments whose classification contradicts elevation direction.
    result: list[Segment] = []
    for sub in sub_segments:
        delta = sub.end_elevation - sub.start_elevation
        if abs(delta) < min_height:
            continue
        # ASCENT must have end > start; DESCENT must have end < start.
        if sub.segment_type == SegmentType.ASCENT and delta <= 0:
            continue
        if sub.segment_type == SegmentType.DESCENT and delta >= 0:
            continue
        result.append(sub)

    return result


def _merge_adjacent_same_direction(
    segments: list[Segment],
    all_points: list[TrackPoint],
) -> list[Segment]:
    """Merge adjacent segments sharing the same SegmentType.

    When merging, the combined segment spans from the first segment's
    first point to the second segment's last point, including all
    original TrackPoints between those positions (looked up from
    *all_points*).
    """
    if not segments:
        return []

    # Build an identity-based index for fast lookup of point positions
    # in the original track.
    point_id_to_idx: dict[int, int] = {id(p): i for i, p in enumerate(all_points)}

    merged: list[Segment] = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        if seg.segment_type == prev.segment_type:
            # Merge: span from prev's first point to seg's last point,
            # including all intermediate TrackPoints from all_points.
            start_idx = point_id_to_idx[id(prev.points[0])]
            end_idx = point_id_to_idx[id(seg.points[-1])]
            merged_points = tuple(all_points[start_idx : end_idx + 1])
            merged[-1] = Segment(
                segment_type=prev.segment_type,
                points=merged_points,
            )
        else:
            merged.append(seg)

    return merged


def _trim_segment_gaps(
    all_points: list[TrackPoint],
    segments: list[Segment],
    flatness_threshold: float,
    time_window: float,
    min_trim_duration: float,
    min_height: float,
    merge_across_interior_gaps: bool,
) -> list[Segment]:
    """Orchestrate gap trimming: boundary trim → interior split → merge.

    Phase 1: Trim leading/trailing flat stretches from each segment.
    Phase 2: Split remaining segments at interior flat stretches.
    Phase 3: Optionally merge adjacent same-direction segments.

    By the time segments reach this function, adjacent same-direction
    candidates have already been merged in :func:`_build_segments`, so
    the only same-direction adjacency Phase 3 can encounter is the
    interior splits produced by Phase 2.  When *merge_across_interior_gaps*
    is ``False``, Phase 3 is skipped so those interior flats remain as
    gaps (trail-running semantics); when ``True``, the pieces are merged
    back into one segment (ski-touring semantics).
    """
    # Phase 1: boundary trimming
    trimmed: list[Segment] = []
    for seg in segments:
        result = _trim_boundaries(seg, time_window, flatness_threshold, min_trim_duration)
        if result is not None:
            trimmed.append(result)

    # Phase 2: interior splitting
    split: list[Segment] = []
    for seg in trimmed:
        split.extend(
            _split_interior_gaps(
                seg, time_window, flatness_threshold, min_trim_duration, min_height
            )
        )

    # Phase 3: merge adjacent same-direction segments (sport-dependent)
    if not merge_across_interior_gaps:
        return split
    return _merge_adjacent_same_direction(split, all_points)


def _build_segments(
    track_points: list[TrackPoint],
    boundary_indices: list[int],
    min_height: float,
) -> list[Segment]:
    """Classify, filter, and merge boundary pairs into segments.

    Walks consecutive pairs of *boundary_indices*, classifies each as
    ASCENT or DESCENT based on elevation change, discards flat and
    trivial segments, and merges adjacent same-direction segments.

    Args:
        track_points: The full ordered list of track points.
        boundary_indices: Sorted indices into *track_points* produced
            by the RDP simplification step.
        min_height: Minimum absolute elevation change for a segment
            to be retained.

    Returns:
        A list of :class:`Segment` values in chronological order.
    """
    if len(boundary_indices) < 2:
        return []

    # --- Step 1: classify and filter ---
    candidates: list[tuple[int, int, SegmentType]] = []
    for k in range(len(boundary_indices) - 1):
        i = boundary_indices[k]
        j = boundary_indices[k + 1]
        delta = track_points[j].elevation - track_points[i].elevation

        if delta == 0.0:
            continue  # flat — discard
        if abs(delta) < min_height:
            continue  # trivial — discard

        seg_type = SegmentType.ASCENT if delta > 0 else SegmentType.DESCENT
        candidates.append((i, j, seg_type))

    if not candidates:
        return []

    # --- Step 2: merge adjacent same-direction candidates ---
    merged: list[tuple[int, int, SegmentType]] = [candidates[0]]
    for start_idx, end_idx, seg_type in candidates[1:]:
        prev_start, prev_end, prev_type = merged[-1]
        if seg_type == prev_type:
            # Extend the previous candidate's end index.
            merged[-1] = (prev_start, end_idx, prev_type)
        else:
            merged.append((start_idx, end_idx, seg_type))

    # --- Step 3: build Segment objects ---
    return [
        Segment(
            segment_type=seg_type,
            points=tuple(track_points[start_idx : end_idx + 1]),
        )
        for start_idx, end_idx, seg_type in merged
    ]


# Default gap-trimming parameters (metric / seconds).
DEFAULT_FLATNESS_THRESHOLD: float = 3.0  # meters
DEFAULT_TIME_WINDOW: float = 60.0  # seconds
DEFAULT_MIN_TRIM_DURATION: float = 120.0  # seconds


def identify_segments(
    points: list[TrackPoint],
    min_height: float,
    sport_profile: SportProfile,
    flatness_threshold: float = DEFAULT_FLATNESS_THRESHOLD,
    time_window: float = DEFAULT_TIME_WINDOW,
    min_trim_duration: float = DEFAULT_MIN_TRIM_DURATION,
) -> list[Segment]:
    """Identify coarse-grained ascending/descending segments.

    Simplifies the elevation-vs-index profile using the Ramer-Douglas-Peucker
    algorithm with *min_height* as the epsilon tolerance, then classifies,
    filters, and merges the resulting boundary pairs into segments.

    Args:
        points: Ordered track points with elevations in meters.
        min_height: Minimum elevation change (in meters) for a portion
            of the track to qualify as a segment.  Also used as the RDP
            epsilon tolerance.
        sport_profile: Sport-specific configuration.  Its
            ``merge_across_interior_gaps`` setting controls whether
            same-direction segments split by an interior flat are merged
            back together (ski touring) or left as gaps (trail running).
        flatness_threshold: Max elevation range (in meters) over a window
            for it to count as flat.  Lower values detect subtler flats.
        time_window: Sliding-window duration (in seconds) used to test
            flatness.
        min_trim_duration: Minimum duration (in seconds) a flat stretch
            must span to be trimmed from a boundary or split out of an
            interior.

    Returns:
        A list of :class:`Segment` values sorted by start time.
    """
    if len(points) < 2 or min_height <= 0:
        return []

    pairs = [(float(i), p.elevation) for i, p in enumerate(points)]
    boundary_indices = _rdp_simplify(pairs, epsilon=min_height)
    segments = _build_segments(points, boundary_indices, min_height)
    segments = _trim_segment_gaps(
        all_points=points,
        segments=segments,
        flatness_threshold=flatness_threshold,
        time_window=time_window,
        min_trim_duration=min_trim_duration,
        min_height=min_height,
        merge_across_interior_gaps=sport_profile.merge_across_interior_gaps,
    )
    return segments
