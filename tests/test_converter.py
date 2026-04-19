"""Property-based tests for the unit converter.

Feature: gpx-segment-report, Property 3: Unit conversion correctness
Validates: Requirements 2.3, 2.4
"""

import math

from hypothesis import given
from hypothesis import strategies as st

from gpx_segment_report.converter import METERS_TO_FEET, convert_elevation
from gpx_segment_report.models import ElevationUnit


@given(v=st.floats(allow_nan=False, allow_infinity=False))
def test_convert_elevation_feet(v: float) -> None:
    """For any elevation v, convert_elevation(v, FEET) == v * 3.28084 within tolerance."""
    result = convert_elevation(v, ElevationUnit.FEET)
    assert math.isclose(result, v * METERS_TO_FEET, rel_tol=1e-9, abs_tol=1e-12)


@given(v=st.floats(allow_nan=False, allow_infinity=False))
def test_convert_elevation_meters(v: float) -> None:
    """For any elevation v, convert_elevation(v, METERS) returns v exactly."""
    result = convert_elevation(v, ElevationUnit.METERS)
    assert result == v
