# Requirements Document

## Introduction

Replace the current single-pass state machine segment detection algorithm in `gpx_segment_report/segments.py` with a Ramer-Douglas-Peucker (RDP) based approach. The current peak/trough detector has known issues: it can miss trailing segments at the end of a track, is sensitive to the threshold value, and does not handle brief pauses (rest stops, ski touring transitions) gracefully. The RDP approach simplifies the elevation-vs-distance profile, uses the remaining vertices as segment boundaries, and classifies each segment between boundaries as ascent or descent. Brief pauses are naturally absorbed because flat spots have low perpendicular distance from the simplified line.

## Glossary

- **Segment_Detector**: The module (`gpx_segment_report/segments.py`) responsible for identifying ascending and descending segments from a list of TrackPoint values.
- **RDP_Algorithm**: The Ramer-Douglas-Peucker line simplification algorithm, a standard computational geometry algorithm that reduces the number of points in a polyline while preserving its overall shape.
- **Epsilon**: The perpendicular distance tolerance parameter for the RDP_Algorithm, expressed in meters internally. Controls how much elevation detail is preserved during simplification.
- **Boundary_Point**: A vertex retained by the RDP_Algorithm after simplification. Consecutive Boundary_Points define segment start and end positions.
- **TrackPoint**: A data object containing a timestamp and an elevation in meters, as defined in `gpx_segment_report/models.py`.
- **Segment**: A data object representing a contiguous ascending or descending portion of a track, containing a SegmentType and an ordered tuple of TrackPoint values.
- **Min_Height_Filter**: A post-simplification filter that discards segments whose absolute elevation change is below a specified threshold.
- **PRL_Unit**: The preferred reporting/display elevation unit (feet or meters) chosen by the user at the CLI level.
- **SportProfile**: A sport-specific configuration object, currently reserved for future use.

## Requirements

### Requirement 1: RDP-Based Segment Boundary Detection

**User Story:** As a user, I want the segment detector to use the Ramer-Douglas-Peucker algorithm to identify segment boundaries, so that segment detection is more robust and handles trailing segments and brief pauses correctly.

#### Acceptance Criteria

1. WHEN a list of TrackPoint values and an Epsilon value are provided, THE Segment_Detector SHALL apply the RDP_Algorithm to the elevation-vs-index profile to produce a simplified set of Boundary_Points.
2. THE Segment_Detector SHALL use consecutive pairs of Boundary_Points as segment start and end positions.
3. THE RDP_Algorithm implementation SHALL follow the standard textbook recursive algorithm or use a well-known library implementation rather than a bespoke approach.
4. WHEN the RDP_Algorithm is applied, THE Segment_Detector SHALL treat each TrackPoint as a 2D point where the x-coordinate is the point index and the y-coordinate is the elevation in meters.

### Requirement 2: Segment Classification

**User Story:** As a user, I want each segment between boundary points to be classified as ascent or descent based on elevation change direction, so that I can distinguish climbing from descending portions of the track.

#### Acceptance Criteria

1. WHEN a segment's end elevation is greater than the segment's start elevation, THE Segment_Detector SHALL classify the segment as ASCENT.
2. WHEN a segment's end elevation is less than the segment's start elevation, THE Segment_Detector SHALL classify the segment as DESCENT.
3. WHEN a segment's end elevation equals the segment's start elevation, THE Segment_Detector SHALL discard the segment (zero elevation change is neither ascent nor descent).

### Requirement 3: Minimum Segment Elevation Change Filter

**User Story:** As a user, I want trivial segments with very small elevation changes to be discarded after RDP simplification, so that the report only contains meaningful segments.

#### Acceptance Criteria

1. AFTER the RDP_Algorithm produces Boundary_Points, THE Segment_Detector SHALL discard any segment whose absolute elevation change between its start and end Boundary_Points is less than the Epsilon value.
2. WHEN adjacent segments are merged due to a discarded trivial segment between them, THE Segment_Detector SHALL combine the adjacent segments of the same direction into a single segment spanning the combined range of TrackPoint values.

### Requirement 4: Backward-Compatible Function Signature

**User Story:** As a developer, I want the `identify_segments()` function to preserve its existing signature, so that callers (including the CLI) require no changes.

#### Acceptance Criteria

1. THE Segment_Detector SHALL expose an `identify_segments(points, min_height, sport_profile)` function that accepts a list of TrackPoint values, a float min_height in meters, and a SportProfile object.
2. THE Segment_Detector SHALL return a `list[Segment]` with the same Segment data model currently defined in `gpx_segment_report/models.py`.
3. THE Segment_Detector SHALL map the `min_height` parameter to the Epsilon tolerance for the RDP_Algorithm.
4. THE Segment_Detector SHALL accept and preserve the `sport_profile` parameter for future use without altering current behavior.

### Requirement 5: Edge Case Handling

**User Story:** As a user, I want the segment detector to handle degenerate inputs gracefully, so that the application does not crash on unusual GPX data.

#### Acceptance Criteria

1. WHEN fewer than 2 TrackPoint values are provided, THE Segment_Detector SHALL return an empty list.
2. WHEN the min_height value is zero or negative, THE Segment_Detector SHALL return an empty list.
3. WHEN all TrackPoint values have identical elevations (a flat track), THE Segment_Detector SHALL return an empty list.
4. WHEN the track consists of a single monotonic ascent or descent whose elevation change meets or exceeds Epsilon, THE Segment_Detector SHALL return exactly one Segment covering the entire track.

### Requirement 6: Segment Structural Invariants

**User Story:** As a developer, I want segments to maintain structural correctness, so that downstream consumers (formatter, chart) can rely on segment data integrity.

#### Acceptance Criteria

1. THE Segment_Detector SHALL return segments in chronological order based on start time.
2. THE Segment_Detector SHALL include all TrackPoint values between a segment's start and end Boundary_Points (inclusive) in the segment's points tuple.
3. THE Segment_Detector SHALL preserve the original input order of TrackPoint values within each segment's points tuple.
4. WHEN consecutive segments share a Boundary_Point, THE Segment_Detector SHALL include the shared Boundary_Point as the last point of the preceding segment and the first point of the following segment.

### Requirement 7: Brief Pause Absorption

**User Story:** As a user, I want brief pauses (rest stops, transitions) to be absorbed into surrounding segments rather than creating spurious segment boundaries, so that the report reflects meaningful elevation changes.

#### Acceptance Criteria

1. WHEN a flat or near-flat portion of the track has a perpendicular distance from the simplified line that is less than Epsilon, THE RDP_Algorithm SHALL absorb the flat portion into the surrounding segment by not retaining it as a Boundary_Point.
2. THE Segment_Detector SHALL not create separate segments for brief pauses that fall below the Epsilon tolerance.

### Requirement 8: Epsilon Parameter Semantics

**User Story:** As a user, I want the epsilon parameter to behave like the existing min-height parameter in terms of units and CLI mapping, so that the transition to the new algorithm is seamless.

#### Acceptance Criteria

1. THE Segment_Detector SHALL accept the Epsilon value in meters internally, consistent with TrackPoint elevation storage.
2. THE CLI SHALL continue to accept `--min-height` in PRL_Unit values and convert to meters before passing to the Segment_Detector, preserving the existing conversion logic.
3. THE CLI SHALL use the same default values for `--min-height` as currently defined (100 feet / 30 meters) when the user does not specify a value.
