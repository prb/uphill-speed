"""Unit conversion utilities for elevation values."""

from gpx_segment_report.models import ElevationUnit

METERS_TO_FEET: float = 3.28084


def convert_elevation(value_meters: float, unit: ElevationUnit) -> float:
    """Convert an elevation from meters to the target unit.

    When unit is METERS, returns value unchanged.
    When unit is FEET, multiplies by METERS_TO_FEET.
    """
    if unit is ElevationUnit.FEET:
        return value_meters * METERS_TO_FEET
    return value_meters


def default_min_height(unit: ElevationUnit) -> float:
    """Return the default minimum height for the given unit.

    Returns 100.0 for feet, 30.0 for meters.
    """
    if unit is ElevationUnit.FEET:
        return 100.0
    return 30.0
