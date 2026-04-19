# Implementation Plan: Segment Gap Trimming

## Overview

Add a post-processing step to the RDP-based segment detection pipeline that detects and removes flat/stagnant stretches from segment boundaries and interiors. All new logic is implemented as private helper functions in `gpx_segment_report/segments.py`. The public `identify_segments()` signature is unchanged.

## Tasks

- [x] 1. Implement flat detection core
  - [x] 1.1 Implement `_is_window_flat()` in `gpx_segment_report/segments.py`
    - Accept `points`, `start_idx`, `end_idx`, `flatness_threshold`
    - Compute `max(elevation) - min(elevation)` over `points[start_idx:end_idx+1]`
    - Return `True` if range ≤ `flatness_threshold`
    - _Requirements: 3.1, 3.2_

  - [x] 1.2 Write property test for `_is_window_flat()`
    - **Property 1: Flat window detection matches elevation range**
    - **Validates: Requirements 3.1, 3.2**
    - Add to `tests/test_segments.py`

- [x] 2. Implement boundary trimming
  - [x] 2.1 Implement `_find_leading_flat()` in `gpx_segment_report/segments.py`
    - Scan forward from index 0 using time-based windows
    - Extend as long as consecutive time windows remain flat
    - Return index of first non-flat point (or `len(points)` if entirely flat)
    - _Requirements: 3.3, 3.5_

  - [x] 2.2 Implement `_find_trailing_flat()` in `gpx_segment_report/segments.py`
    - Mirror of leading flat, scanning backward from last point
    - Return index one past the last non-flat point (or 0 if entirely flat)
    - _Requirements: 3.4, 3.5_

  - [x] 2.3 Implement `_trim_boundaries()` in `gpx_segment_report/segments.py`
    - Apply `_find_leading_flat()` and `_find_trailing_flat()` to a single segment
    - Only trim if flat stretch duration ≥ `min_trim_duration`
    - Return trimmed `Segment` or `None` if consumed (fewer than 2 points remain)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 2.4 Write property test for boundary trimming
    - **Property 2: Boundary trimming removes flat edges and preserves active content**
    - **Validates: Requirements 1.3, 1.4, 1.6**
    - Generate segments with synthetic flat prefix/suffix of known duration and random active middle
    - Add to `tests/test_segments.py`

- [x] 3. Implement interior gap detection and splitting
  - [x] 3.1 Implement `_find_interior_flat_stretches()` in `gpx_segment_report/segments.py`
    - Slide a time window across segment interior
    - Record flat stretches meeting `min_trim_duration`
    - Return list of `(start_idx, end_idx)` tuples for flat regions
    - Only return stretches fully interior (not touching first or last point)
    - _Requirements: 2.1, 2.5, 3.1, 3.2, 3.5_

  - [x] 3.2 Implement `_split_interior_gaps()` in `gpx_segment_report/segments.py`
    - Split segment at each interior flat stretch
    - Inherit original segment classification for sub-segments
    - Discard sub-segments with `|Δelev|` < `min_height`
    - Discard sub-segments whose classification contradicts elevation direction
    - _Requirements: 2.2, 2.3, 2.4, 6.4, 6.5_

  - [x] 3.3 Write property test for interior flat splitting
    - **Property 3: Interior flat stretches cause segment splitting**
    - **Validates: Requirements 2.2, 2.5**
    - Generate segments with synthetic interior flat stretch of known duration and random active bookends
    - Add to `tests/test_segments.py`

- [x] 4. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement merge and orchestrator
  - [x] 5.1 Implement `_merge_adjacent_same_direction()` in `gpx_segment_report/segments.py`
    - Merge consecutive segments sharing the same `SegmentType`
    - Use `all_points` list to include all intermediate TrackPoints in merged segment
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 5.2 Implement `_trim_segment_gaps()` orchestrator in `gpx_segment_report/segments.py`
    - Phase 1: `_trim_boundaries()` on each segment
    - Phase 2: `_split_interior_gaps()` on each trimmed segment
    - Phase 3: `_merge_adjacent_same_direction()` on results
    - _Requirements: 5.1, 5.4, 5.5_

  - [x] 5.3 Integrate `_trim_segment_gaps()` into `identify_segments()`
    - Call after `_build_segments()` with default parameters: `flatness_threshold=3.0`, `time_window=60.0`, `min_trim_duration=120.0`
    - Pass `min_height` through for sub-segment filtering
    - _Requirements: 4.4, 5.1, 5.2, 5.3_

- [x] 6. Checkpoint
  - Ensure all existing tests in `tests/test_segments.py` and `tests/test_segments_unit.py` still pass. Ask the user if questions arise.

- [x] 7. Write remaining property tests
  - [x] 7.1 Write property test for no-flat passthrough
    - **Property 4: Segments without flat stretches pass through unchanged**
    - **Validates: Requirements 5.3**
    - Generate segments with steep monotonic elevation (guaranteed no flat windows)
    - Add to `tests/test_segments.py`

  - [x] 7.2 Write property test for contiguous subsequence invariant
    - **Property 5: Trimmed segment points are contiguous subsequences of the input**
    - **Validates: Requirements 6.2, 6.3, 7.3**
    - Random elevation profiles through full pipeline, verify output point contiguity
    - Add to `tests/test_segments.py`

  - [x] 7.3 Write property test for no consecutive same-direction segments
    - **Property 6: No consecutive same-direction segments in output**
    - **Validates: Requirements 7.1**
    - Random elevation profiles through full pipeline, verify no adjacent same-type segments
    - Add to `tests/test_segments.py`

- [x] 8. Write unit tests for edge cases and known shapes
  - [x] 8.1 Write unit tests for boundary trimming scenarios in `tests/test_segments_unit.py`
    - `test_trim_no_flat_stretches`: segments with no flat regions pass through unchanged
    - `test_trim_leading_flat`: known leading flat stretch is trimmed
    - `test_trim_trailing_flat`: known trailing flat stretch is trimmed
    - `test_trim_both_edges`: both leading and trailing flat stretches trimmed
    - `test_trim_consumes_segment`: entirely flat segment is discarded
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 8.2 Write unit tests for interior splitting scenarios in `tests/test_segments_unit.py`
    - `test_interior_split_single`: single interior flat stretch splits segment into two
    - `test_interior_split_multiple`: multiple interior flat stretches produce multiple sub-segments
    - `test_split_discards_tiny_subsegment`: sub-segment below min_height after split is discarded
    - `test_split_discards_contradictory_classification`: sub-segment with wrong elevation direction is discarded
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 6.4, 6.5_

  - [x] 8.3 Write unit tests for merge and edge cases in `tests/test_segments_unit.py`
    - `test_merge_after_trim`: adjacent same-direction segments after trimming are merged
    - `test_non_uniform_timestamps`: flat detection uses timestamps, not index count
    - `test_short_flat_below_min_duration`: flat stretch shorter than min_trim_duration is NOT trimmed
    - `test_flat_exactly_at_threshold`: elevation range exactly equal to flatness_threshold is classified as flat
    - _Requirements: 3.2, 3.5, 4.3, 7.1_

- [x] 9. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- All new code goes in `gpx_segment_report/segments.py` as private helper functions
- No new modules or dependencies are introduced
- The public `identify_segments()` signature is unchanged
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Existing tests must continue to pass after integration (backward compatibility)
