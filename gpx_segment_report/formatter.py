"""Report formatter for GPX segment data."""

from gpx_segment_report.converter import convert_elevation
from gpx_segment_report.models import ElevationUnit, Segment

HEADER = "start_time\tend_time\ttype\ttotal_time\tstart_elevation\tend_elevation\trate"


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds as HH:MM:SS."""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_report(segments: list[Segment], unit: ElevationUnit) -> str:
    """Format segments into a tabular report string.

    Columns: start_time (ISO 8601), end_time (ISO 8601), type (ascent/descent),
    total_time (HH:MM:SS), start_elevation (PRL), end_elevation (PRL),
    rate (PRL/hour).

    Returns header row even when segments list is empty.
    """
    sorted_segments = sorted(segments, key=lambda s: s.start_time)
    lines = [HEADER]

    for seg in sorted_segments:
        start_iso = seg.start_time.isoformat()
        end_iso = seg.end_time.isoformat()
        seg_type = seg.segment_type.value
        duration_secs = (seg.end_time - seg.start_time).total_seconds()
        total_time = _format_duration(duration_secs)
        start_elev = convert_elevation(seg.start_elevation, unit)
        end_elev = convert_elevation(seg.end_elevation, unit)
        hours = duration_secs / 3600.0
        rate = abs(end_elev - start_elev) / hours if hours > 0 else 0.0
        lines.append(
            f"{start_iso}\t{end_iso}\t{seg_type}\t{total_time}"
            f"\t{start_elev:.1f}\t{end_elev:.1f}\t{rate:.1f}"
        )

    return "\n".join(lines)
