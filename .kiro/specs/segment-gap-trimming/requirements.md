# Requirements Document

## Introduction

After the RDP-based segment detection pipeline (`simplify → segment → filter → merge`) produces segments, flat or stagnant stretches at segment boundaries are absorbed into adjacent segments because their perpendicular distance from the simplified line falls below epsilon. While this is correct RDP behavior, these flat spots — rest stops, transitions between skinning and skiing, slow starts — should visually appear as gaps (grey/unsegmented regions on the chart) rather than being part of an ascent or descent segment.

This feature adds a post-processing step that detects and trims these flat stretches from segment boundaries, splitting them into gaps. Two complementary detection strategies are used: (1) scanning fixed-size windows at segment edges for stagnant elevation, and (2) scanning the interior of segments with a sliding time window to find prolonged flat regions that warrant splitting.

The post-processing step operates on the output of `identify_segments()` in `gpx_segment_report/segments.py`, preserving the existing RDP pipeline and public API.

## Glossary

- **Gap_Trimmer**: The post-processing module responsible for detecting and removing flat stretches from segment boundaries and interiors, producing trimmed segments and gaps.
- **Segment_Detector**: The existing module (`gpx_segment_report/segments.py`) that identifies ascending and descending segments using the RDP pipeline.
- **Flat_Stretch**: A contiguous sequence of TrackPoint values within a segment where the absolute elevation change over the stretch is at or below the Flatness_Threshold.
- **Flatness_Threshold**: The maximum absolute elevation change (in meters) over a time window for a stretch to be considered flat. A configurable parameter.
- **Time_Window**: The duration (in seconds) over which elevation change is measured to detect flat stretches. A configurable parameter.
- **Boundary_Trim**: The process of scanning from the start or end of a segment inward to detect and remove a leading or trailing Flat_Stretch.
- **Interior_Split**: The process of scanning the interior of a segment with a sliding Time_Window to find a Flat_Stretch that warrants splitting the segment into two segments with a gap between them.
- **Gap**: A region of the track that is not covered by any segment. Gaps appear as grey/unsegmented regions on the elevation profile chart.
- **TrackPoint**: A data object containing a timestamp and an elevation in meters, as defined in `gpx_segment_report/models.py`.
- **Segment**: A data object representing a contiguous ascending or descending portion of a track, containing a SegmentType and an ordered tuple of TrackPoint values.
- **Min_Trim_Duration**: The minimum duration (in seconds) that a detected Flat_Stretch must span before it qualifies for trimming. Prevents trimming very brief pauses.

## Requirements

### Requirement 1: Post-RDP Boundary Trimming

**User Story:** As a user, I want flat stretches at the start or end of segments to be trimmed into gaps, so that rest stops and transitions at segment boundaries do not inflate segment durations or distort elevation change rates.

#### Acceptance Criteria

1. AFTER the Segment_Detector produces segments, THE Gap_Trimmer SHALL scan from the start of each segment inward to detect a leading Flat_Stretch.
2. AFTER the Segment_Detector produces segments, THE Gap_Trimmer SHALL scan from the end of each segment inward to detect a trailing Flat_Stretch.
3. WHEN a leading Flat_Stretch is detected whose duration meets or exceeds Min_Trim_Duration, THE Gap_Trimmer SHALL remove the Flat_Stretch from the segment by advancing the segment start to the first TrackPoint after the Flat_Stretch.
4. WHEN a trailing Flat_Stretch is detected whose duration meets or exceeds Min_Trim_Duration, THE Gap_Trimmer SHALL remove the Flat_Stretch from the segment by retreating the segment end to the last TrackPoint before the Flat_Stretch.
5. WHEN both a leading and trailing Flat_Stretch are detected in the same segment, THE Gap_Trimmer SHALL trim both independently.
6. IF trimming a Flat_Stretch would reduce a segment to fewer than 2 TrackPoint values, THEN THE Gap_Trimmer SHALL discard the entire segment.

### Requirement 2: Time-Based Interior Gap Detection

**User Story:** As a user, I want prolonged flat regions inside a segment to be detected and split into gaps, so that stagnant periods mid-segment (e.g., a long rest partway through a climb) create visible gap regions on the chart.

#### Acceptance Criteria

1. AFTER boundary trimming is complete, THE Gap_Trimmer SHALL scan the interior of each remaining segment using a sliding Time_Window to detect Flat_Stretches.
2. WHEN a Flat_Stretch is detected in the interior of a segment whose duration meets or exceeds Min_Trim_Duration, THE Gap_Trimmer SHALL split the segment at the Flat_Stretch boundaries, producing two sub-segments with a gap between them.
3. WHEN a segment is split, THE Gap_Trimmer SHALL classify each resulting sub-segment using the same ASCENT or DESCENT classification as the original segment.
4. IF a resulting sub-segment after splitting has an absolute elevation change less than the min_height threshold, THEN THE Gap_Trimmer SHALL discard that sub-segment.
5. WHEN multiple interior Flat_Stretches are detected within a single segment, THE Gap_Trimmer SHALL split at each one, processing from earliest to latest.

### Requirement 3: Flat Stretch Detection Algorithm

**User Story:** As a developer, I want a clear and consistent algorithm for detecting flat stretches, so that the detection logic is predictable and testable.

#### Acceptance Criteria

1. THE Gap_Trimmer SHALL detect a Flat_Stretch by measuring the absolute difference between the maximum and minimum elevation values within a sliding window of duration Time_Window.
2. WHEN the elevation range (max minus min) within the Time_Window is at or below the Flatness_Threshold, THE Gap_Trimmer SHALL classify that window as flat.
3. WHEN detecting a leading Flat_Stretch, THE Gap_Trimmer SHALL start the window at the segment's first TrackPoint and extend it forward as long as consecutive windows remain flat.
4. WHEN detecting a trailing Flat_Stretch, THE Gap_Trimmer SHALL start the window at the segment's last TrackPoint and extend it backward as long as consecutive windows remain flat.
5. THE Gap_Trimmer SHALL use TrackPoint timestamps to measure window duration, not point count or index distance.

### Requirement 4: Configuration Parameters

**User Story:** As a user, I want to control the sensitivity of gap detection through configurable parameters, so that I can tune the behavior for different activities and terrain.

#### Acceptance Criteria

1. THE Gap_Trimmer SHALL accept a Flatness_Threshold parameter expressed in meters.
2. THE Gap_Trimmer SHALL accept a Time_Window parameter expressed in seconds.
3. THE Gap_Trimmer SHALL accept a Min_Trim_Duration parameter expressed in seconds.
4. THE Gap_Trimmer SHALL use default values when parameters are not explicitly provided: Flatness_Threshold of 3.0 meters, Time_Window of 60 seconds, Min_Trim_Duration of 120 seconds.
5. WHERE the CLI exposes gap trimming parameters, THE CLI SHALL convert user-provided elevation values from the selected PRL_Unit to meters before passing them to the Gap_Trimmer.

### Requirement 5: Preservation of Existing Pipeline and API

**User Story:** As a developer, I want the gap trimming step to integrate cleanly with the existing RDP pipeline without modifying the public API or breaking existing behavior.

#### Acceptance Criteria

1. THE Gap_Trimmer SHALL operate as a post-processing step on the output of `identify_segments()`, not modify the RDP pipeline internals.
2. THE Segment_Detector SHALL continue to expose the same `identify_segments(points, min_height, sport_profile)` function signature.
3. WHEN gap trimming is disabled or no flat stretches are detected, THE Gap_Trimmer SHALL return the segments unchanged.
4. THE Gap_Trimmer SHALL accept the full list of TrackPoint values and the list of Segment values produced by `identify_segments()` as inputs.
5. THE Gap_Trimmer SHALL return a `list[Segment]` with the same Segment data model currently defined in `gpx_segment_report/models.py`.

### Requirement 6: Trimmed Segment Structural Invariants

**User Story:** As a developer, I want trimmed segments to maintain the same structural invariants as untrimmed segments, so that downstream consumers (formatter, chart) can rely on segment data integrity.

#### Acceptance Criteria

1. THE Gap_Trimmer SHALL return segments in chronological order based on start time.
2. THE Gap_Trimmer SHALL preserve the original input order of TrackPoint values within each segment's points tuple.
3. WHEN a segment is trimmed, THE Gap_Trimmer SHALL produce a segment whose points tuple is a contiguous subsequence of the original segment's points tuple.
4. WHEN a segment is trimmed, THE Gap_Trimmer SHALL produce a segment whose classification (ASCENT or DESCENT) matches the elevation direction of the trimmed segment (end elevation vs. start elevation).
5. IF trimming causes a segment's classification to contradict its elevation direction (e.g., an ASCENT segment where end elevation is less than start elevation after trimming), THEN THE Gap_Trimmer SHALL discard that segment.

### Requirement 7: Post-Trim Merge Pass

**User Story:** As a developer, I want a merge pass after gap trimming to consolidate any adjacent same-direction segments that may result from discarding intermediate segments.

#### Acceptance Criteria

1. AFTER all trimming and splitting operations are complete, THE Gap_Trimmer SHALL merge adjacent segments that share the same SegmentType.
2. WHEN merging two adjacent segments, THE Gap_Trimmer SHALL combine their TrackPoint ranges into a single segment spanning from the first segment's start to the second segment's end.
3. WHEN merging two adjacent segments, THE Gap_Trimmer SHALL include all TrackPoint values from the original input list between the merged segment's start and end indices (inclusive).

### Requirement 8: Chart Gap Visualization

**User Story:** As a user, I want gaps created by trimming to appear as grey/unsegmented regions on the elevation profile chart, so that I can visually distinguish active segments from rest periods.

#### Acceptance Criteria

1. WHEN the chart is rendered with trimmed segments, THE Chart_Module SHALL leave regions not covered by any segment uncolored (no ascent or descent fill), allowing the default background to show through.
2. THE Chart_Module SHALL not require any modification to render gaps correctly, because gaps are defined as the absence of segment coverage and the existing rendering logic already only fills regions covered by segments.
