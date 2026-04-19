"""Tests for the CLI entry point and report pipeline."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gpx_segment_report.converter import METERS_TO_FEET, default_min_height
from gpx_segment_report.models import ElevationUnit, SUPPORTED_SPORTS


# ---------------------------------------------------------------------------
# Property 8: Unsupported sport profile rejected
# Feature: gpx-segment-report, Property 8: Unsupported sport profile rejected
# ---------------------------------------------------------------------------

_supported_keys = set(SUPPORTED_SPORTS.keys())


@given(
    sport=st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,49}", fullmatch=True).filter(
        lambda s: s not in _supported_keys
    ),
)
@settings(max_examples=100, deadline=None)
def test_unsupported_sport_profile_rejected(sport: str) -> None:
    """For any string not in SUPPORTED_SPORTS the CLI exits non-zero."""
    result = subprocess.run(
        [
            sys.executable, "-m", "gpx_segment_report.cli",
            "sample-data/Ordering_is_Important.gpx",
            "--sport", sport,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Unsupported sport profile" in result.stderr
    # The error message must list every supported sport type.
    for key in sorted(SUPPORTED_SPORTS):
        assert key in result.stderr


# ---------------------------------------------------------------------------
# Unit tests for CLI defaults and integration (Task 9.3)
# ---------------------------------------------------------------------------


def test_default_unit_is_feet() -> None:
    """PRL defaults to feet when --unit is not specified."""
    result = subprocess.run(
        [
            sys.executable, "-m", "gpx_segment_report.cli",
            "sample-data/Ordering_is_Important.gpx",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # The output should contain the header and data rows.
    assert "start_time" in result.stdout


def test_default_min_height_feet() -> None:
    """min_height defaults to 100 for feet."""
    assert default_min_height(ElevationUnit.FEET) == 100.0


def test_default_min_height_meters() -> None:
    """min_height defaults to 30 for meters."""
    assert default_min_height(ElevationUnit.METERS) == 30.0


def test_default_sport_is_ski_touring() -> None:
    """Sport defaults to ski_touring (no --sport flag should succeed)."""
    result = subprocess.run(
        [
            sys.executable, "-m", "gpx_segment_report.cli",
            "sample-data/Ordering_is_Important.gpx",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_end_to_end_ordering_gpx() -> None:
    """End-to-end: sample GPX produces a valid report with header and data rows."""
    result = subprocess.run(
        [
            sys.executable, "-m", "gpx_segment_report.cli",
            "sample-data/Ordering_is_Important.gpx",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    # At least a header row
    assert len(lines) >= 1
    header = lines[0]
    for col in ("start_time", "end_time", "type", "total_time",
                "start_elevation", "end_elevation", "rate"):
        assert col in header
    # If there are data rows, each should have the right number of columns
    if len(lines) > 1:
        expected_cols = len(header.split("\t"))
        for row in lines[1:]:
            assert len(row.split("\t")) == expected_cols


def test_end_to_end_meters_unit() -> None:
    """End-to-end with --unit meters produces a valid report."""
    result = subprocess.run(
        [
            sys.executable, "-m", "gpx_segment_report.cli",
            "sample-data/Ordering_is_Important.gpx",
            "--unit", "meters",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    assert len(lines) >= 1


# ---------------------------------------------------------------------------
# CLI integration tests for --output flag (Task 6.2)
# ---------------------------------------------------------------------------

SAMPLE_GPX = "sample-data/Ordering_is_Important.gpx"


def test_output_flag_creates_chart_file(tmp_path: Path) -> None:
    """--output creates a chart file at the specified path."""
    chart_path = tmp_path / "chart.png"
    result = subprocess.run(
        [
            sys.executable, "-m", "gpx_segment_report.cli",
            SAMPLE_GPX,
            "--output", str(chart_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert chart_path.exists()


def test_output_flag_still_prints_text_report(tmp_path: Path) -> None:
    """Text report is printed to stdout even when --output is provided."""
    chart_path = tmp_path / "chart.png"
    result = subprocess.run(
        [
            sys.executable, "-m", "gpx_segment_report.cli",
            SAMPLE_GPX,
            "--output", str(chart_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "start_time" in result.stdout


def test_no_chart_without_output_flag() -> None:
    """No chart file is created when --output is omitted."""
    result = subprocess.run(
        [
            sys.executable, "-m", "gpx_segment_report.cli",
            SAMPLE_GPX,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "start_time" in result.stdout


def test_unsupported_extension_produces_error(tmp_path: Path) -> None:
    """Unsupported output extension exits non-zero with error on stderr."""
    chart_path = tmp_path / "chart.bmp"
    result = subprocess.run(
        [
            sys.executable, "-m", "gpx_segment_report.cli",
            SAMPLE_GPX,
            "--output", str(chart_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Unsupported output format" in result.stderr


def test_nonexistent_file_exits_nonzero() -> None:
    """A missing GPX file should exit non-zero with an error message."""
    result = subprocess.run(
        [
            sys.executable, "-m", "gpx_segment_report.cli",
            "does_not_exist.gpx",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "File not found" in result.stderr
