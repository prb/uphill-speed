This application will extract a report from a GPX track as follows:

- The report will support both `feet` and `meters` for altitudes and rates.  The choice of feet or meters is on a per-report basis and will be passed into the report generation process as a parameter with a default of `feet`.  This is referred to as "PRL" below, for "per report length".
- The report will support a minimum height parameter (specified in PRL units) for what can constitute an ascent or descent segment.  The default is either 30 meters or 100 feet, depending on the PRL. 
- The report will support a sport-specific parameter to help with the identification of segments.  The initial sport will be `ski touring`, but we exepct to add `trail running`.
- The report will output rates in terms of per hour measurents, e.g., feet/hour.
- The report will have the following columns: starting timestamp (as an IOSO8601 datetime), ending timestamp, segment type (ascent or descent), total time (hours:minutes:seconds), starting elevation (PRL), ending elevation (PRL), rate of gain/loss in PRL.
- Identify the climbing and descending segments within the track.  The track may have brief ascents within the descents and vice versa, so there's a need to identify the more coarse-grained segments within the track.  Note that a track may not be entirely composed of ascents and descents, and a track might contain no useful segments (e.g., a flat run on a running track).  
- For each ascent or descent segment, add a row to the report.

In terms of invariants and expectations:

- We expect the file to contain altitudes (in meters or in feet) and will exit with an informative error if it does not.

The application will be developed in Python aligned with practices as outlined in project documents.