# gpx-segment-report

A command-line tool that parses GPX 1.1 track files and produces a tabular report of climbing and descending segments, along with optional elevation profile charts.

![Example elevation profile chart](images/example-chart.png)

## What it does

Given a GPX track with elevation data, `gpx-segment-report`:

1. Identifies coarse-grained ascending and descending segments using a Ramer-Douglas-Peucker simplification pipeline
2. Trims flat/stagnant stretches (rest stops, transitions) from segment boundaries, and — depending on the sport profile — splits interior flats out as gaps
3. Outputs a tab-separated report with timestamps, elevations, durations, and gain/loss rates
4. Optionally generates an elevation profile chart (PNG or SVG) with colored ascent/descent fills

## Installation

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

```bash
# Basic report (feet, default settings)
uv run gpx-segment-report track.gpx

# Report in meters
uv run gpx-segment-report track.gpx --unit meters

# Custom minimum segment height (in PRL units)
uv run gpx-segment-report track.gpx --min-height 150

# Generate an elevation profile chart
uv run gpx-segment-report track.gpx --output chart.png

# Trail-running profile, tuned to break out small flat spots
uv run gpx-segment-report track.gpx --sport trail_running \
    --flatness-threshold 30 --time-window 90 --min-trim-duration 90
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--unit`, `-u` | Elevation unit: `feet` or `meters` | `feet` |
| `--min-height`, `-m` | Minimum elevation change to qualify as a segment (in chosen unit) | 100 ft / 30 m |
| `--sport`, `-s` | Sport profile: `ski_touring` or `trail_running` (see below) | `ski_touring` |
| `--output`, `-o` | Save elevation profile chart to file (.png or .svg) | — |
| `--flatness-threshold`, `-f` | Max elevation range (in chosen unit) over a window for it to count as flat; lower values detect subtler flats | ~10 ft / 3 m |
| `--time-window`, `-w` | Sliding-window duration in seconds used to test flatness | 60 |
| `--min-trim-duration`, `-t` | Minimum duration in seconds a flat stretch must span to be trimmed or split out | 120 |

### Sport profiles

The `--sport` profile controls how flat stretches *inside* a climb or descent are
treated:

- **`ski_touring`** (default) merges across interior flats, so a flat traverse
  mid-climb stays part of the surrounding ascent. This produces coarse,
  skin-track-style segments.
- **`trail_running`** leaves interior flats as gaps, splitting the surrounding
  segment in two. This surfaces short flat spots (shelves, false summits,
  benches) as distinct breaks.

### Detecting flat spots

Flat-spot sensitivity is governed by `--flatness-threshold`, `--time-window`, and
`--min-trim-duration`. A stretch counts as a flat (and is trimmed from boundaries
or split out of interiors) when its elevation range stays within the flatness
threshold across the time window for at least the minimum trim duration.

To surface small flats on a running track, pair `trail_running` with a larger
threshold and a shorter minimum duration:

```bash
# Break out shelves of ~30 ft range lasting 90s or more
uv run gpx-segment-report track.gpx --sport trail_running \
    --flatness-threshold 30 --time-window 90 --min-trim-duration 90
```

### Example output

```
start_time                        end_time                          type     total_time  start_elevation  end_elevation  rate
2026-04-17T17:40:06+00:00         2026-04-17T19:40:09+00:00         ascent   02:00:03    5452.1           8376.0         1461.3
2026-04-17T19:50:44+00:00         2026-04-17T20:30:47+00:00         descent  00:40:03    8370.7           6430.4         2906.8
```

## Running tests

```bash
uv run pytest
```

The test suite includes both property-based tests (Hypothesis) and unit tests covering segment detection, gap trimming, formatting, and chart generation.

## License

[MIT](LICENSE)
