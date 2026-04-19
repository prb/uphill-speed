# Requirements Document

## Introduction

The Graphical Output feature extends the GPX Segment Report application with visual representations of track elevation data and identified segments. Currently the application produces only a text-based tabular report. This feature adds the ability to generate elevation profile charts that visually depict the track's elevation over time, with identified ascending and descending segments highlighted using distinct colors. The graphical output complements the existing text report, giving users an at-a-glance understanding of their activity's elevation profile and segment breakdown.

## Glossary

- **Chart_Generator**: The component responsible for producing graphical elevation profile charts from track point data and identified segments.
- **Elevation_Profile**: A line chart plotting elevation (y-axis) against time (x-axis) for all track points in a GPX file.
- **Segment_Overlay**: A visual layer on the Elevation_Profile that highlights identified ascending and descending segments using distinct fill colors beneath the elevation line.
- **Output_File**: The image file written to disk containing the rendered chart. Supported formats include PNG and SVG.
- **PRL**: Per Report Length — the elevation unit (feet or meters) selected for a given report run (inherited from the existing application).
- **Report_Generator**: The top-level component that orchestrates GPX parsing, segment identification, report formatting, and chart generation.
- **Track_Point**: A single data point from a GPX track containing a timestamp and an elevation value.
- **Segment**: A contiguous portion of a GPX track classified as either ascending or descending (as defined in the existing application).

## Requirements

### Requirement 1: Generate Elevation Profile Chart

**User Story:** As a user, I want to see a visual elevation profile of my GPX track so that I can quickly understand the terrain and elevation changes of my activity.

#### Acceptance Criteria

1. WHEN a GPX file is processed and track points are available, THE Chart_Generator SHALL produce an Elevation_Profile plotting elevation on the y-axis and time on the x-axis.
2. THE Chart_Generator SHALL label the y-axis with the elevation unit matching the PRL parameter (e.g., "Elevation (feet)" or "Elevation (meters)").
3. THE Chart_Generator SHALL label the x-axis with time values derived from track point timestamps.
4. THE Chart_Generator SHALL display all track points as a continuous line on the Elevation_Profile.
5. THE Chart_Generator SHALL use elevation values converted to PRL units for the y-axis.

### Requirement 2: Highlight Segments on Chart

**User Story:** As a user, I want ascending and descending segments visually highlighted on the elevation profile so that I can see where the application identified climbs and descents.

#### Acceptance Criteria

1. WHEN segments have been identified, THE Chart_Generator SHALL render a Segment_Overlay on the Elevation_Profile for each identified segment.
2. THE Chart_Generator SHALL use a visually distinct fill color for ascent segments and a different visually distinct fill color for descent segments.
3. THE Chart_Generator SHALL fill the area beneath the elevation line within each segment's time range to indicate the segment boundaries.
4. WHEN a track contains zero identified segments, THE Chart_Generator SHALL render the Elevation_Profile without any Segment_Overlay.
5. THE Chart_Generator SHALL include a legend identifying the fill colors used for ascent and descent segments.

### Requirement 3: Save Chart to Output File

**User Story:** As a user, I want to save the elevation profile chart to an image file so that I can share it or include it in reports.

#### Acceptance Criteria

1. THE Chart_Generator SHALL write the rendered chart to an Output_File at a path specified by the user.
2. WHEN the output file path ends with ".png", THE Chart_Generator SHALL save the chart in PNG format.
3. WHEN the output file path ends with ".svg", THE Chart_Generator SHALL save the chart in SVG format.
4. IF the output file path uses an unsupported file extension, THEN THE Chart_Generator SHALL exit with an informative error message listing the supported formats (PNG, SVG).
5. IF the output file path refers to a directory that does not exist, THEN THE Chart_Generator SHALL exit with an informative error message indicating the directory was not found.

### Requirement 4: Integrate Chart Generation with CLI

**User Story:** As a user, I want to generate a chart from the command line alongside or instead of the text report so that I can choose my preferred output format.

#### Acceptance Criteria

1. THE Report_Generator SHALL accept an optional output file path parameter for chart generation via the command-line interface.
2. WHEN the output file path parameter is provided, THE Report_Generator SHALL generate the chart and save it to the specified path.
3. WHEN the output file path parameter is provided, THE Report_Generator SHALL also produce the text report to standard output.
4. WHEN the output file path parameter is not provided, THE Report_Generator SHALL produce only the text report to standard output without generating a chart.

### Requirement 5: Configure Chart Appearance

**User Story:** As a user, I want the chart to have a clear, readable appearance so that the elevation profile and segments are easy to interpret.

#### Acceptance Criteria

1. THE Chart_Generator SHALL render the chart with a title containing the GPX file name.
2. THE Chart_Generator SHALL use a fixed chart size of 12 inches wide by 6 inches tall.
3. THE Chart_Generator SHALL render axis tick labels and the chart title in a legible font size.
4. THE Chart_Generator SHALL use a grid overlay on the chart to aid in reading elevation and time values.
