# Requirements Document

## Introduction

The GPX Segment Report application parses GPX 1.1 track files and produces a tabular report of climbing and descending segments. The application identifies coarse-grained ascending and descending segments within a track, smoothing over brief reversals caused by GPS noise or minor terrain undulations. Each identified segment (ascent or descent) becomes a row in the report. The report supports configurable elevation units (feet or meters), a minimum height threshold for segment identification, and sport-specific segmentation parameters starting with ski touring.

## Glossary

- **Report_Generator**: The top-level component that orchestrates GPX parsing, segment identification, and report output.
- **GPX_Parser**: The component responsible for reading and parsing GPX 1.1 files using the gpxpy library, extracting track points with timestamps and elevations.
- **Segment_Identifier**: The component that analyzes a sequence of track points and identifies coarse-grained ascending and descending segments, filtering out brief reversals that fall below the minimum height threshold.
- **Unit_Converter**: The component responsible for converting elevation values between meters and feet.
- **PRL**: Per Report Length — the elevation unit (feet or meters) selected for a given report run.
- **Minimum_Height**: The minimum elevation change (in PRL units) required for a portion of the track to qualify as a distinct segment. Defaults to 100 feet when PRL is feet, or 30 meters when PRL is meters.
- **Segment**: A contiguous portion of a GPX track classified as either ascending or descending after smoothing out brief reversals below the Minimum_Height threshold.
- **Ascent_Segment**: A Segment where the overall elevation trend is upward.
- **Descent_Segment**: A Segment where the overall elevation trend is downward.
- **Sport_Profile**: A named configuration that provides sport-specific thresholds for segment identification. The initial Sport_Profile is "ski touring".
- **Track_Point**: A single data point from a GPX track containing at minimum a timestamp and an elevation value.

## Requirements

### Requirement 1: Parse GPX Files

**User Story:** As a user, I want to load a GPX 1.1 file so that the application can extract track point data for segment analysis.

#### Acceptance Criteria

1. WHEN a valid GPX 1.1 file path is provided, THE GPX_Parser SHALL parse the file and return an ordered sequence of Track_Point values containing timestamp and elevation.
2. WHEN a GPX file contains elevation values in meters, THE GPX_Parser SHALL preserve the original meter values for downstream processing.
3. IF a GPX file does not contain elevation data for one or more track points, THEN THE GPX_Parser SHALL exit with an informative error message indicating the absence of elevation data.
4. IF the provided file path does not exist or is not a valid GPX file, THEN THE GPX_Parser SHALL exit with an informative error message.

### Requirement 2: Convert Elevation Units

**User Story:** As a user, I want to choose between feet and meters for my report so that I can read elevations in my preferred unit.

#### Acceptance Criteria

1. THE Report_Generator SHALL accept a PRL parameter specifying the elevation unit as either "feet" or "meters".
2. THE Report_Generator SHALL default the PRL parameter to "feet" when no unit is specified.
3. WHEN PRL is set to "feet", THE Unit_Converter SHALL convert elevation values from meters to feet using the factor 1 meter = 3.28084 feet.
4. WHEN PRL is set to "meters", THE Unit_Converter SHALL pass elevation values through without conversion.

### Requirement 3: Configure Minimum Height Threshold

**User Story:** As a user, I want to set a minimum elevation change for segment identification so that insignificant elevation variations do not produce spurious segments.

#### Acceptance Criteria

1. THE Report_Generator SHALL accept a Minimum_Height parameter specifying the minimum elevation change (in PRL units) required for a track portion to qualify as a segment.
2. WHEN PRL is set to "feet" and no Minimum_Height is specified, THE Report_Generator SHALL default the Minimum_Height to 100 feet.
3. WHEN PRL is set to "meters" and no Minimum_Height is specified, THE Report_Generator SHALL default the Minimum_Height to 30 meters.
4. THE Segment_Identifier SHALL disregard elevation changes smaller than the Minimum_Height when identifying segments.

### Requirement 4: Support Sport-Specific Segmentation

**User Story:** As a user, I want sport-specific segment identification so that the segmentation behavior matches the characteristics of my activity.

#### Acceptance Criteria

1. THE Report_Generator SHALL accept a Sport_Profile parameter specifying the sport type.
2. THE Report_Generator SHALL default the Sport_Profile parameter to "ski touring" when no sport is specified.
3. WHEN the Sport_Profile is "ski touring", THE Segment_Identifier SHALL use thresholds appropriate for ski touring to distinguish real elevation trend changes from brief reversals.
4. IF an unsupported Sport_Profile value is provided, THEN THE Report_Generator SHALL exit with an informative error message listing the supported sport types.

### Requirement 5: Identify Coarse-Grained Segments

**User Story:** As a user, I want the application to identify meaningful climbing and descending segments so that brief GPS noise or minor undulations do not fragment the report.

#### Acceptance Criteria

1. WHEN a sequence of Track_Point values is provided, THE Segment_Identifier SHALL classify contiguous portions of the track as either ascending or descending based on the overall elevation trend.
2. THE Segment_Identifier SHALL absorb brief reversals (short ascents within a descent or short descents within an ascent) that fall below the Minimum_Height threshold, merging them into the surrounding segment.
3. THE Segment_Identifier SHALL produce segments that, when concatenated, account for all track points that belong to identified segments without gaps or overlaps.
4. THE Segment_Identifier SHALL preserve the original track point order within each segment.
5. WHEN a track contains no elevation changes exceeding the Minimum_Height threshold, THE Segment_Identifier SHALL return zero segments.
6. THE Segment_Identifier SHALL allow portions of the track that are neither a qualifying ascent nor a qualifying descent to remain unassigned to any segment.

### Requirement 6: Generate Segment Report

**User Story:** As a user, I want a tabular report of all identified segments so that I can review my climbing and descending performance.

#### Acceptance Criteria

1. THE Report_Generator SHALL produce a report containing one row for each Segment (ascent or descent) identified in the track.
2. THE Report_Generator SHALL include the following columns in each row: starting timestamp (ISO 8601 format), ending timestamp (ISO 8601 format), segment type ("ascent" or "descent"), total time (HH:MM:SS), starting elevation (in PRL units), ending elevation (in PRL units), and elevation rate (PRL units per hour).
3. THE Report_Generator SHALL compute total time as the difference between the ending timestamp and the starting timestamp of the Segment.
4. THE Report_Generator SHALL compute elevation rate as the absolute elevation change divided by the total time expressed in hours.
5. THE Report_Generator SHALL order report rows chronologically by starting timestamp.
6. WHEN a track contains zero identified Segments, THE Report_Generator SHALL produce an empty report with column headers only.

### Requirement 7: Validate Track Data

**User Story:** As a user, I want clear error messages when my GPX file lacks required data so that I understand what went wrong.

#### Acceptance Criteria

1. IF a GPX file contains no track segments, THEN THE Report_Generator SHALL exit with an informative error message indicating the file contains no track data.
2. IF a GPX file contains track points without timestamps, THEN THE Report_Generator SHALL exit with an informative error message indicating the absence of timestamp data.
