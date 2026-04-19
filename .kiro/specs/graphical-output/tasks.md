# Implementation Plan: Graphical Output

## Overview

Add elevation profile chart generation to the GPX Segment Report CLI. Implementation proceeds in four stages: add the matplotlib dependency, build the chart module with its internal helper and public API, wire it into the CLI, and write tests. Each stage is independently verifiable.

## Tasks

- [x] 1. Add matplotlib dependency
  - Add `matplotlib` to the `[project.dependencies]` list in `pyproject.toml`
  - Run `uv lock` to update `uv.lock`
  - _Requirements: 1.1_

- [x] 2. Implement chart module
  - [x] 2.1 Create `gpx_segment_report/chart.py` with constants and internal `_build_figure` helper
    - Define module-level constants: `FIGURE_WIDTH`, `FIGURE_HEIGHT`, `ASCENT_COLOR`, `DESCENT_COLOR`, `ASCENT_ALPHA`, `DESCENT_ALPHA`, `LINE_COLOR`, `SUPPORTED_FORMATS`
    - Implement `_build_figure(points, segments, unit, gpx_filename) -> Figure` that:
      - Creates a 12×6 inch figure
      - Converts elevations to PRL units via `convert_elevation()`
      - Plots elevation vs time as a continuous line
      - Adds `fill_between` overlays for each segment with ascent/descent colors
      - Sets title containing `gpx_filename`, y-axis label with unit, x-axis time labels
      - Adds legend with "Ascent" and "Descent" entries
      - Enables grid overlay
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4_

  - [x] 2.2 Implement public `generate_chart()` function
    - Validate output path extension against `SUPPORTED_FORMATS`; raise `ValueError` for unsupported extensions
    - Validate parent directory exists; raise `ValueError` if missing
    - Call `_build_figure()` to get the figure
    - Save figure with `savefig()` using format inferred from extension
    - Close figure to free memory
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 2.3 Write property test: Plotted data correctness (Property 1)
    - **Property 1: Plotted data correctness**
    - Generate random track point lists and elevation units via Hypothesis
    - Call `_build_figure` and inspect `ax.get_lines()[0].get_ydata()` — verify length equals number of track points and each y-value matches `convert_elevation(point.elevation, unit)` within tolerance
    - Minimum 100 examples
    - **Validates: Requirements 1.1, 1.4, 1.5**

  - [x] 2.4 Write property test: Segment overlay correspondence (Property 2)
    - **Property 2: Segment overlay correspondence**
    - Generate random segments and track points via Hypothesis
    - Call `_build_figure` and inspect `ax.collections` — verify one `PolyCollection` per segment and each spans the correct time range
    - Minimum 100 examples
    - **Validates: Requirements 2.1, 2.3**

  - [x] 2.5 Write property test: Segment overlay color consistency (Property 3)
    - **Property 3: Segment overlay color consistency**
    - Generate mixed ascent/descent segments via Hypothesis
    - Inspect fill colors of `ax.collections` — all ascent overlays share one color, all descent overlays share a different color, and the two are distinct
    - Minimum 100 examples
    - **Validates: Requirements 2.2**

  - [x] 2.6 Write property test: Chart title contains filename (Property 7)
    - **Property 7: Chart title contains filename**
    - Generate random filename strings via Hypothesis
    - Call `_build_figure` and verify `ax.get_title()` contains the filename
    - Minimum 100 examples
    - **Validates: Requirements 5.1**

  - [x] 2.7 Write property test: Figure size invariant (Property 8)
    - **Property 8: Figure size invariant**
    - Generate arbitrary valid inputs via Hypothesis
    - Call `_build_figure` and verify `fig.get_size_inches()` equals `(12, 6)`
    - Minimum 100 examples
    - **Validates: Requirements 5.2**

- [x] 3. Checkpoint - Ensure chart module tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement file output validation and tests
  - [x] 4.1 Write property test: Output file format correctness (Property 4)
    - **Property 4: Output file format correctness**
    - Generate valid track data and use `tmp_path` for output
    - Call `generate_chart` with `.png` and `.svg` paths
    - Verify PNG files start with `\x89PNG` magic bytes; SVG files contain `<svg` markup
    - Minimum 100 examples
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [x] 4.2 Write property test: Unsupported extension rejection (Property 5)
    - **Property 5: Unsupported extension rejection**
    - Generate output paths with extensions not in `{".png", ".svg"}` via Hypothesis
    - Verify `generate_chart` raises `ValueError` with message listing supported formats
    - Minimum 100 examples
    - **Validates: Requirements 3.4**

  - [x] 4.3 Write property test: Missing directory rejection (Property 6)
    - **Property 6: Missing directory rejection**
    - Generate output paths under non-existent parent directories via Hypothesis
    - Verify `generate_chart` raises `ValueError` with message indicating directory not found
    - Minimum 100 examples
    - **Validates: Requirements 3.5**

  - [x] 4.4 Write unit tests for chart module
    - Test y-axis label contains "feet" or "meters" matching the unit (Req 1.2)
    - Test legend includes "Ascent" and "Descent" entries (Req 2.5)
    - Test chart renders without overlays when segments list is empty (Req 2.4)
    - Test grid is enabled on axes (Req 5.4)
    - _Requirements: 1.2, 2.4, 2.5, 5.4_

- [x] 5. Checkpoint - Ensure all chart tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Integrate chart generation with CLI
  - [x] 6.1 Add `--output` / `-o` argument to CLI
    - Add optional `--output` / `-o` argument to `argparse` in `cli.py`
    - When `args.output` is provided, call `generate_chart()` after printing the text report
    - Pass `points`, `segments`, `unit`, `args.output`, and the GPX filename to `generate_chart`
    - Existing `except (GpxParseError, ValueError)` handler already covers chart errors — no error handling changes needed
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 6.2 Write CLI integration tests for `--output` flag
    - Test that `--output` flag is accepted and chart file is created at specified path
    - Test that text report is still printed to stdout when `--output` is provided
    - Test that no chart file is created when `--output` is omitted
    - Test that unsupported extension produces error message on stderr
    - Add tests to `tests/test_cli.py`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 3.4_

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests inspect the matplotlib object model programmatically (no image comparison)
- The internal `_build_figure` helper enables property testing without file I/O
- Checkpoints ensure incremental validation
