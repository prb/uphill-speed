# Implementation Plan: GPX Segment Report

## Overview

Incrementally build the GPX segment report application as a Python pipeline: project setup → data models → unit converter → GPX parser → segment identifier → report formatter → CLI entry point. Each step builds on the previous, with property-based and unit tests woven in close to the code they validate.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Initialize the project with `uv init` and configure `pyproject.toml`
  - Add dependencies: `gpxpy` for GPX parsing
  - Add dev dependencies: `pytest`, `hypothesis` for testing
  - Set `exclude-newer` to `P3D` in `[tool.uv]`
  - Create the package directory `gpx_segment_report/` with `__init__.py`
  - Create the test directory `tests/` with `__init__.py`
  - _Requirements: Project standards (PEP-8, type hinting, uv, pytest)_

- [x] 2. Implement data models and enums
  - [x] 2.1 Create `gpx_segment_report/models.py`
    - Define `ElevationUnit` enum with `FEET` and `METERS` values
    - Define `SegmentType` enum with `ASCENT` and `DESCENT` values
    - Define frozen `TrackPoint` dataclass with `timestamp: datetime` and `elevation: float` (meters)
    - Define frozen `Segment` dataclass with `segment_type`, `points` tuple, and computed properties (`start_time`, `end_time`, `start_elevation`, `end_elevation`)
    - Define frozen `SportProfile` dataclass and `SUPPORTED_SPORTS` dict with `ski_touring`
    - Define `GpxParseError` exception class
    - _Requirements: 1.1, 2.1, 4.1, 4.2, 5.1_

- [x] 3. Implement unit converter
  - [x] 3.1 Create `gpx_segment_report/converter.py`
    - Implement `convert_elevation(value_meters, unit)` using factor 3.28084
    - Implement `default_min_height(unit)` returning 100.0 for feet, 30.0 for meters
    - _Requirements: 2.3, 2.4, 3.2, 3.3_

  - [x] 3.2 Write property test for unit conversion (Property 3)
    - **Property 3: Unit conversion correctness**
    - For any elevation value v: `convert_elevation(v, FEET)` equals `v * 3.28084` within tolerance, and `convert_elevation(v, METERS)` equals `v` exactly
    - Create `tests/test_converter.py`
    - **Validates: Requirements 2.3, 2.4**

- [x] 4. Implement GPX parser
  - [x] 4.1 Create `gpx_segment_report/parser.py`
    - Implement `parse_gpx(file_path)` using `gpxpy.parse()`
    - Iterate over `gpx.tracks → track.segments → segment.points`
    - Extract elevation and timestamp from each point into `TrackPoint` values
    - Raise `GpxParseError` for: file not found, invalid GPX XML, missing elevation, missing timestamps, no track segments
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 7.1, 7.2_

  - [x] 4.2 Write property test for parser round-trip (Property 1)
    - **Property 1: Parser round-trip preserves track points**
    - Generate random (timestamp, elevation) sequences, construct valid GPX XML, parse it, and verify the returned TrackPoint values match
    - Create `tests/test_parser.py`
    - **Validates: Requirements 1.1, 1.2**

  - [x] 4.3 Write property test for parser rejection of missing elevation (Property 2)
    - **Property 2: Parser rejects GPX data missing elevation**
    - Generate GPX XML with one or more points missing `<ele>`, verify `GpxParseError` is raised
    - Add to `tests/test_parser.py`
    - **Validates: Requirements 1.3**

  - [x] 4.4 Write unit tests for parser error cases
    - Test non-existent file path raises `GpxParseError`
    - Test invalid GPX XML raises `GpxParseError`
    - Test GPX with no track segments raises `GpxParseError`
    - Test GPX with missing timestamps raises `GpxParseError`
    - Add to `tests/test_parser.py`
    - _Requirements: 1.3, 1.4, 7.1, 7.2_

- [x] 5. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement segment identifier
  - [x] 6.1 Create `gpx_segment_report/segments.py`
    - Implement `identify_segments(points, min_height, sport_profile)` using the state-machine algorithm from the design
    - Track current direction (ascending/descending/idle), segment start index, peak/trough elevations, and reversal accumulator
    - Absorb brief reversals below `min_height` into the surrounding segment
    - Finalize in-progress segments at end of track if they meet the `min_height` threshold
    - `min_height` is received in meters (converted at the boundary before calling)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 3.4_

  - [x] 6.2 Write property test for minimum height enforcement (Property 4)
    - **Property 4: Minimum height threshold enforced on segments**
    - For any track points and positive min_height, every returned segment has `|end_elevation - start_elevation| >= min_height`
    - Create `tests/test_segments.py`
    - **Validates: Requirements 3.4, 5.2**

  - [x] 6.3 Write property test for segment classification (Property 5)
    - **Property 5: Segment classification matches elevation trend**
    - For any returned segment: ASCENT implies `end_elevation > start_elevation`, DESCENT implies `end_elevation < start_elevation`
    - Add to `tests/test_segments.py`
    - **Validates: Requirements 5.1**

  - [x] 6.4 Write property test for segment structural invariants (Property 6)
    - **Property 6: Segment structural invariants**
    - Verify: (a) points within each segment preserve input order, (b) no point appears in multiple segments, (c) consecutive segments are chronologically ordered in the input
    - Add to `tests/test_segments.py`
    - **Validates: Requirements 5.3, 5.4, 5.6**

  - [x] 6.5 Write property test for flat tracks (Property 7)
    - **Property 7: Flat tracks produce zero segments**
    - For any track points where `max(elevation) - min(elevation) < min_height`, verify empty result
    - Add to `tests/test_segments.py`
    - **Validates: Requirements 5.5**

- [x] 7. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement report formatter
  - [x] 8.1 Create `gpx_segment_report/formatter.py`
    - Implement `format_report(segments, unit)` producing a tabular string
    - Columns: start_time (ISO 8601), end_time (ISO 8601), type (ascent/descent), total_time (HH:MM:SS), start_elevation (PRL), end_elevation (PRL), rate (PRL/hour)
    - Use `convert_elevation()` to convert meter values to PRL at display time
    - Return header row when segments list is empty
    - Order rows chronologically by start time
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 8.2 Write property test for report row count and order (Property 9)
    - **Property 9: Report row count and chronological order**
    - For any list of segments, verify exactly `len(segments)` data rows and chronological ordering
    - Create `tests/test_formatter.py`
    - **Validates: Requirements 6.1, 6.5**

  - [x] 8.3 Write property test for report field completeness (Property 10)
    - **Property 10: Report rows contain all required fields**
    - For any segment, verify the row contains valid ISO 8601 timestamps, segment type, HH:MM:SS time, elevations, and rate
    - Add to `tests/test_formatter.py`
    - **Validates: Requirements 6.2**

  - [x] 8.4 Write property test for report computation correctness (Property 11)
    - **Property 11: Report computation correctness**
    - Verify total_time equals `end_time - start_time` as HH:MM:SS, and rate equals `abs(elevation_change) / hours` within tolerance
    - Add to `tests/test_formatter.py`
    - **Validates: Requirements 6.3, 6.4**

- [x] 9. Implement CLI entry point and wire pipeline
  - [x] 9.1 Create `gpx_segment_report/cli.py`
    - Implement `main()` using `argparse` with: `file` (positional), `--unit`/`-u` (feet|meters, default feet), `--min-height`/`-m` (optional), `--sport`/`-s` (default ski_touring)
    - Validate sport profile against `SUPPORTED_SPORTS`, raise `ValueError` with supported list if invalid
    - Convert user-specified `min_height` from PRL to meters when PRL is feet
    - Apply default `min_height` via `default_min_height(unit)` when not specified
    - Orchestrate pipeline: parse → identify segments → format report → print
    - Catch `GpxParseError` and `ValueError`, print to stderr, exit non-zero
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4_

  - [x] 9.2 Write property test for unsupported sport profile (Property 8)
    - **Property 8: Unsupported sport profile rejected**
    - For any string not in `SUPPORTED_SPORTS`, verify the report generator raises an error listing supported types
    - Create `tests/test_cli.py`
    - **Validates: Requirements 4.4**

  - [x] 9.3 Write unit tests for CLI defaults and integration
    - Test PRL defaults to feet when not specified
    - Test min_height defaults to 100 for feet, 30 for meters
    - Test sport defaults to ski_touring
    - Test end-to-end with `sample-data/Ordering_is_Important.gpx` produces a valid report
    - Add to `tests/test_cli.py`
    - _Requirements: 2.2, 3.2, 3.3, 4.2_

- [x] 10. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Elevations are stored internally in meters; conversion happens at boundaries only (CLI input and report output)
