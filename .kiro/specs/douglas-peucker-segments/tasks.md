# Implementation Plan: Douglas-Peucker Segments

## Overview

Replace the internals of `identify_segments()` in `gpx_segment_report/segments.py` with the four-stage RDP pipeline (simplify → segment → filter → merge). The public signature stays the same. All new helpers are private functions in the same module. Existing tests must continue to pass.

## Tasks

- [x] 1. Implement RDP helper functions
  - [x] 1.1 Implement `_perpendicular_distance(point, line_start, line_end)`
    - Compute perpendicular distance from a 2D point to a line segment using the cross-product formula
    - Handle the degenerate case where `line_start == line_end` by returning Euclidean distance
    - Input/output types: `tuple[float, float]` → `float`
    - _Requirements: 1.3, 1.4_

  - [x] 1.2 Implement `_rdp_simplify(points, epsilon)`
    - Standard recursive Ramer-Douglas-Peucker on `list[tuple[float, float]]`
    - Returns `list[int]` — sorted indices of retained points
    - Base case: ≤ 2 points → return both endpoint indices
    - Recursive case: find max perpendicular distance point; if ≥ epsilon, recurse on both halves and merge
    - Uses `_perpendicular_distance` from task 1.1
    - _Requirements: 1.1, 1.3, 1.4_

  - [ ] 1.3 Write property test for RDP idempotency
    - **Property 7: RDP simplification is idempotent**
    - Applying `_rdp_simplify` twice produces the same retained indices as applying it once
    - Generator: random `(index, elevation)` pair lists, random epsilon
    - **Validates: Requirement 1.1**

  - [ ] 1.4 Write unit test for `_perpendicular_distance` degenerate case
    - Test that when `line_start == line_end`, the function returns Euclidean distance to the point
    - _Requirements: 1.3_

- [x] 2. Implement `_build_segments` and rewire `identify_segments`
  - [x] 2.1 Implement `_build_segments(track_points, boundary_indices, min_height)`
    - Walk consecutive pairs of boundary indices
    - Classify each pair as ASCENT (Δelev > 0), DESCENT (Δelev < 0), or discard (Δelev == 0)
    - Filter: discard segments with `|Δelev| < min_height`
    - Merge: combine adjacent same-direction segments by extending `end_idx`
    - Build `Segment` objects with `points = tuple(track_points[start_idx : end_idx + 1])`
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 6.2, 6.3, 6.4_

  - [x] 2.2 Rewire `identify_segments()` to use the new pipeline
    - Keep the existing guard: `len(points) < 2 or min_height <= 0 → []`
    - Build `(index, elevation)` pairs from `points`
    - Call `_rdp_simplify(pairs, epsilon=min_height)`
    - Call `_build_segments(points, boundary_indices, min_height)`
    - Remove the old state-machine code and `_Direction` enum and `_maybe_finalize` helper
    - Preserve `sport_profile` parameter (accepted but unused)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 8.1_

- [x] 3. Checkpoint
  - Ensure existing tests in `tests/test_segments.py` still pass with the new implementation
  - Run `uv run pytest tests/test_segments.py` and verify all 4 existing property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Add new property-based tests
  - [ ] 4.1 Write property test for classification matches elevation direction
    - **Property 1: Classification matches elevation direction**
    - Every ASCENT has `end_elevation > start_elevation`; every DESCENT has `end_elevation < start_elevation`
    - Generator: random elevation lists (size 2–200), random min_height
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [ ] 4.2 Write property test for no consecutive same-direction segments
    - **Property 3: No consecutive same-direction segments**
    - No two adjacent returned segments share the same `segment_type`
    - Generator: random elevation lists, random min_height
    - **Validates: Requirement 3.2**

  - [ ] 4.3 Write property test for monotonic tracks produce one segment
    - **Property 6: Monotonic tracks produce exactly one segment**
    - Strictly monotonic elevation sequences with total change ≥ min_height → exactly 1 segment
    - Generator: strictly increasing/decreasing elevation sequences
    - **Validates: Requirement 5.4**

- [x] 5. Add unit tests for edge cases
  - [x] 5.1 Write unit tests for edge cases and known shapes
    - `test_empty_input`: 0 points → `[]`
    - `test_single_point`: 1 point → `[]`
    - `test_zero_min_height`: min_height=0 → `[]`
    - `test_negative_min_height`: min_height=-5 → `[]`
    - `test_simple_v_shape`: known V-shaped elevation → 1 descent + 1 ascent
    - `test_simple_peak`: known peak elevation → 1 ascent + 1 descent
    - `test_trivial_segment_filtered`: small bump below min_height is discarded
    - `test_merge_after_filter`: two ascents separated by a trivial descent merge into one ascent
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 2.1, 2.2, 3.1, 3.2_

- [x] 6. Final checkpoint
  - Run full test suite: `uv run pytest tests/`
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Existing property tests in `tests/test_segments.py` (Properties 4, 5, 6, 7 from the original spec) are algorithm-agnostic and must continue to pass
- New tests go in `tests/test_segments.py` alongside existing tests
- No new modules, dependencies, or data models are introduced
- The `sport_profile` parameter is preserved but unused by the algorithm
