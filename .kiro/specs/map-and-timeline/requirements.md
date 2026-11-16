# Map and timeline: requirements

Plan task: 3.6 (offline map and timeline linked to articles); 3.9 for states and accessibility. Depends on: content-pipeline
(coordinates, timeline data, map tiles in the pack), the article reader (plan 3.2) and search (for finding places).
Steering: product, tech, license-record, cite-or-refuse.

## Introduction
The atlas and the timeline are the two features that carry the encyclopedia identity. The map shows where things are in
Liberia and West Africa; the timeline shows when things happened. Both work with no network on a low-end Android phone,
and both are linked to the articles, so a student can move from a place or a date to the text that explains it.

Glossary
- **Place article**: an article that has coordinates in the pack manifest.
- **Event**: one entry on the timeline: a date or period, a title, a one-sentence description, a linked passage and optional place.
- **Era**: a named period used to group events (for example "Early states and trade", "Colonization and settlement").
- **Map pack**: the vector tile file and map style, fonts and sprites stored in the pack.
- **Fallback map**: a simple SVG map used when the WebGL map cannot run or low-power mode is on.

## Requirements

### R1. Offline map
**User story:** As a student, I want to see Liberia and West Africa on a map and tap places to read about them, even with no connection.
1. THE map screen SHALL show Liberia and the surrounding West African countries from tiles stored in the pack, with no network request.
2. THE map SHALL support pan, pinch zoom and double-tap zoom on a touch screen, and buttons for zoom in, zoom out and "reset to Liberia".
3. THE map SHALL show markers for place articles, grouped into clusters at low zoom, with the cluster count readable.
4. WHEN the student taps a marker, THE app SHALL open a bottom sheet with the article title, its first sentence, its heading, and buttons "Read article" and "Show events here".
5. THE map SHALL label countries, capitals, major cities and water bodies in English, and SHALL use neutral wording for disputed or changed borders (the base data and its source are recorded in the manifest).
6. THE map SHALL show only the current, modern base map. Historical borders are out of scope; historical places appear as markers with a note.

### R2. Map data and fallback
1. THE map pack SHALL cover West Africa at overview detail and Liberia at street level, within the size budget in design.md.
2. THE map pack SHALL record every dataset, license and attribution in the manifest, including OpenStreetMap contributors (ODbL) where used, and the app SHALL show the required attribution on the map.
3. IF WebGL is unavailable, the map fails to start, or low-power mode is on, THEN THE app SHALL show the fallback SVG map with the same markers and bottom sheet, and SHALL say which map is in use.
4. THE fallback map SHALL work with no map tiles and no WebGL, at a few hundred kilobytes.

### R3. Timeline
**User story:** As a student, I want a clear timeline of Liberian and African history so that I can see what came before and after.
1. THE timeline screen SHALL list events in date order, grouped under era headings, in a single vertical list that works on a phone screen.
2. EACH event SHALL show its date or period, its title, one sentence of description and a source badge; "Read article" opens the linked article at the linked passage.
3. THE timeline SHALL support events with an exact year, a year range, an approximate date ("about 1500") and dates before the common era.
4. THE timeline SHALL let the student filter by era and by subject, and jump to a decade or century through a quick scrubber.
5. WHEN an event has a place, THE event SHALL show "Show on map".
6. THE timeline SHALL contain at least 60 events for pack v1 (Liberian and African history), each reviewed by the subject expert before release.

### R4. Linking
1. FROM an article, THE reader SHALL show "On the map" when the article has coordinates, and "On the timeline" when events link to it.
2. FROM a map marker, THE sheet SHALL list up to 5 events tied to that place.
3. FROM a timeline event, "Show on map" SHALL open the map centered on the place with that marker selected.
4. THE links SHALL work from the search results as well: a result that is a place article shows a small map icon.
5. THE back button and gestures SHALL return the student to where they were, with map position and timeline scroll restored.

### R5. Cite or refuse for events
1. EACH timeline event SHALL link to a passage id that exists in the pack, and the event's one-sentence description SHALL be either copied from that passage or written by the project's own words and marked as "summary of the passage".
2. THE validator SHALL fail the build if an event has no resolvable passage, an invalid date, or a place without coordinates.
3. THE app SHALL NOT display an event whose passage link does not resolve.

### R6. Performance and device limits
1. THE map SHALL open in under 3 seconds on the demo Android phone after the first load, and keep at least 24 frames per second while panning.
2. THE timeline SHALL render the first screen in under 500 ms and scroll without dropped frames using list virtualization.
3. THE map tiles SHALL be read by range request from a single file in the pack so that memory stays within the budget in design.md.
4. WHEN the device is in low-power mode, THE app SHALL use the fallback map, reduce animation and keep the timeline.

### R7. States and accessibility
1. THE screens SHALL have designed states: map loading, map failed (fallback shown), no places in view, timeline empty after filters (with "clear filters"), and event detail.
2. THE map SHALL be usable without gestures: marker list view, keyboard focus on markers, and text alternatives for map content.
3. THE timeline and map SHALL support screen readers, text scaling, high contrast and reduced motion.
4. THE app SHALL send no network requests and SHALL store no personal data for these screens.

## Out of scope
Historical border maps, routing and directions, user location (GPS), satellite imagery, drawing on the map, editing or adding events, languages other than English.
