"""Elevation profile chart generation for GPX track data."""

from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from gpx_segment_report.converter import convert_elevation  # noqa: E402
from gpx_segment_report.models import (  # noqa: E402
    ElevationUnit,
    Segment,
    SegmentType,
    TrackPoint,
)

# ---------------------------------------------------------------------------
# Chart configuration constants
# ---------------------------------------------------------------------------

FIGURE_WIDTH: int = 12
FIGURE_HEIGHT: int = 8

ASCENT_COLOR: str = "#2ecc71"
DESCENT_COLOR: str = "#e74c3c"

ASCENT_ALPHA: float = 0.3
DESCENT_ALPHA: float = 0.3

LINE_COLOR: str = "#2c3e50"

SUPPORTED_FORMATS: set[str] = {".png", ".svg"}


def _plain_datetime(dt: datetime) -> datetime:
    """Return a plain ``datetime`` with a stdlib tzinfo.

    gpxpy uses ``SimpleTZ`` whose ``__eq__`` crashes when matplotlib
    compares it with ``None``.  Replacing it with the stdlib
    ``datetime.timezone`` equivalent avoids the conflict.
    """
    from datetime import timezone

    tz = timezone(dt.utcoffset()) if dt.utcoffset() is not None else None
    return dt.replace(tzinfo=tz)


def _build_figure(
    points: list[TrackPoint],
    segments: list[Segment],
    unit: ElevationUnit,
    gpx_filename: str,
) -> Figure:
    """Build a matplotlib Figure with the elevation profile and segment overlays.

    Args:
        points: Ordered track points (elevations in meters).
        segments: Identified ascending/descending segments.
        unit: Elevation unit for y-axis values and label.
        gpx_filename: Original GPX file name shown in the chart title.

    Returns:
        A fully configured matplotlib ``Figure`` ready for display or saving.
    """
    import matplotlib.dates as mdates

    from matplotlib.gridspec import GridSpec

    # Layout: elevation profile on top, numbered segment bar in the middle,
    # reference table at the bottom (when segments exist).
    has_segments = len(segments) > 0
    if has_segments:
        # Scale table height with segment count
        table_ratio = max(1.5, len(segments) * 0.35)
        fig = Figure(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT + table_ratio), constrained_layout=True)
        gs = GridSpec(3, 1, height_ratios=[4, 0.35, table_ratio], figure=fig)
        ax = fig.add_subplot(gs[0])
        ax_bar = fig.add_subplot(gs[1], sharex=ax)
        ax_table = fig.add_subplot(gs[2])
    else:
        fig = Figure(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT), constrained_layout=True)
        ax = fig.add_subplot(111)
        ax_bar = None
        ax_table = None

    # Convert elevations to the requested unit.
    # Ensure timestamps are plain datetime objects so matplotlib's unit
    # handling does not conflict with gpxpy's custom time wrappers.
    times = [_plain_datetime(p.timestamp) for p in points]
    elevations = [convert_elevation(p.elevation, unit) for p in points]

    # Plot the continuous elevation line
    ax.plot(times, elevations, color=LINE_COLOR, linewidth=1.5)

    # Set y-axis to the data range with a small margin
    elev_min = min(elevations)
    elev_max = max(elevations)
    margin = (elev_max - elev_min) * 0.05 or 10.0
    y_floor = elev_min - margin
    ax.set_ylim(bottom=y_floor, top=elev_max + margin)

    # Add fill_between overlays for each segment
    for seg in segments:
        seg_times = [_plain_datetime(p.timestamp) for p in seg.points]
        seg_elevations = [convert_elevation(p.elevation, unit) for p in seg.points]

        if seg.segment_type is SegmentType.ASCENT:
            color = ASCENT_COLOR
            alpha = ASCENT_ALPHA
        else:
            color = DESCENT_COLOR
            alpha = DESCENT_ALPHA

        ax.fill_between(seg_times, y_floor, seg_elevations, color=color, alpha=alpha)

    # Title and axis labels
    ax.set_title(f"Elevation Profile — {gpx_filename}")
    ax.set_ylabel(f"Elevation ({unit.value})")

    # Legend — always show Ascent and Descent entries
    legend_patches = [
        Patch(facecolor=ASCENT_COLOR, alpha=ASCENT_ALPHA, label="Ascent"),
        Patch(facecolor=DESCENT_COLOR, alpha=DESCENT_ALPHA, label="Descent"),
    ]
    ax.legend(handles=legend_patches)

    # Grid overlay
    ax.grid(True)

    # --- Numbered segment bar + reference table ---
    if ax_bar is not None and segments:
        table_rows: list[list[str]] = []

        for idx, seg in enumerate(segments, start=1):
            start = _plain_datetime(seg.start_time)
            end = _plain_datetime(seg.end_time)
            duration_secs = (seg.end_time - seg.start_time).total_seconds()
            duration_hrs = duration_secs / 3600.0
            start_elev = convert_elevation(seg.start_elevation, unit)
            end_elev = convert_elevation(seg.end_elevation, unit)
            rate = abs(end_elev - start_elev) / duration_hrs if duration_hrs > 0 else 0.0

            # Format duration as H:MM:SS
            total_int = int(duration_secs)
            hrs, remainder = divmod(total_int, 3600)
            mins, secs = divmod(remainder, 60)
            duration_str = f"{hrs}:{mins:02d}:{secs:02d}"

            # Draw bar (neutral gray, no segment-type color)
            ax_bar.barh(
                y=0, width=mdates.date2num(end) - mdates.date2num(start),
                left=mdates.date2num(start), height=0.6,
                color="#d5d8dc", alpha=0.8, edgecolor="white", linewidth=0.5,
            )
            # Number label centered in bar
            mid = mdates.num2date(
                (mdates.date2num(start) + mdates.date2num(end)) / 2
            )
            ax_bar.text(
                mid, 0, str(idx),
                ha="center", va="center", fontsize=8, fontweight="bold",
                color="#2c3e50",
            )

            # Collect table row
            table_rows.append([
                str(idx),
                seg.segment_type.value,
                duration_str,
                f"{start_elev:,.0f}",
                f"{end_elev:,.0f}",
                f"{rate:,.0f}",
            ])

        ax_bar.set_yticks([])
        ax_bar.set_ylabel("#", rotation=0, labelpad=10, va="center")
        ax_bar.set_xlabel("Time")
        ax_bar.grid(True, axis="x")
        ax_bar.xaxis_date()
        ax_bar.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax_bar.tick_params(axis="x", labelsize=8, rotation=30)
        plt.setp(ax.get_xticklabels(), visible=False)

        # --- Reference table ---
        ax_table.axis("off")
        col_labels = ["#", "Type", "Duration", f"Start ({unit.value})",
                       f"End ({unit.value})", f"Rate ({unit.value}/hr)"]
        col_widths = [0.05, 0.12, 0.15, 0.18, 0.18, 0.22]
        table = ax_table.table(
            cellText=table_rows,
            colLabels=col_labels,
            colWidths=col_widths,
            loc="center",
            cellLoc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.2)

        # Color-code the type column cells
        for row_idx, seg in enumerate(segments):
            color = ASCENT_COLOR if seg.segment_type is SegmentType.ASCENT else DESCENT_COLOR
            table[row_idx + 1, 1].set_facecolor(color)
            table[row_idx + 1, 1].set_alpha(0.3)
    else:
        ax.set_xlabel("Time")

    return fig


def generate_chart(
    points: list[TrackPoint],
    segments: list[Segment],
    unit: ElevationUnit,
    output_path: str,
    gpx_filename: str,
) -> None:
    """Render an elevation profile chart and save it to disk.

    Args:
        points: Ordered track points (elevations in meters).
        segments: Identified ascending/descending segments.
        unit: Elevation unit for y-axis labeling and values.
        output_path: Destination file path (.png or .svg).
        gpx_filename: Original GPX file name for the chart title.

    Raises:
        ValueError: If the file extension is unsupported or the
                    parent directory does not exist.
    """
    path = Path(output_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported output format '{ext}'. Supported: .png, .svg"
        )

    parent = path.parent
    if not parent.exists():
        raise ValueError(f"Output directory not found: {parent}")

    fig = _build_figure(points, segments, unit, gpx_filename)
    try:
        fig.savefig(output_path)
    finally:
        plt.close(fig)
