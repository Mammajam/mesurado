# Map and timeline: tasks

Each task names the requirements it satisfies and the plan task it advances. Commit with the plan id.
Cut order (plan): quizzes go before the map and timeline, so this is cut last; within it, drop the map detail zoom before the fallback map.

- [ ] 1. Spike on the demo Android phone (plan 0.4, 3.6)
  - [ ] 1.1 Render a Liberia PMTiles extract with MapLibre GL JS on the phone: first open time, frame rate, memory, WebGL support. Record in `eval/results/map-spike.md`. _R1, R6_
  - [ ] 1.2 Measure the SVG fallback map: size and render time. Decide the default for low-memory phones. _R2.3, R2.4_

- [ ] 2. Data (plan 2.x, 3.6)
  - [ ] 2.1 Pipeline: extract place coordinates into the manifest for place articles. _pipeline R10_
  - [ ] 2.2 Build `map.pmtiles` from Natural Earth and the Liberia OSM extract; style, glyphs, sprites; record datasets and licenses in the manifest. _R1.1, R2.1, R2.2_
  - [x] 2.3 Generate the SVG fallback map from simplified Natural Earth. _R2.3_
  - [ ] 2.4 Write `timeline.yaml`: eras and at least 60 events with passage links; build `timeline.json`. _R3.6, R5.1_
  - [ ] 2.5 Validator checks for events (passage, date, place coordinates). _R5.2_
  - [ ] 2.6 Subject expert reviews events and era names. _R3.6_

- [ ] 3. Map view (plan 3.6)
  - [ ] 3.1 `MapView` interface with MapLibre implementation and PMTiles loading from the pack. _R1_
  - [ ] 3.2 `FallbackMap` implementation with the same interface and markers. _R2.3_
  - [ ] 3.3 Start check (5-second timeout), low-power rule, settings switch for "simple map". _R2.3, R6.4_
  - [ ] 3.4 Marker clustering in a worker; marker bottom sheet; marker list view. _R1.3, R1.4, R7.2_
  - [ ] 3.5 Attribution on the map and on the attribution screen. _R2.2_
  - [ ] 3.6 Property tests: clustering conserves markers; markers inside viewport. _R1.3_

- [ ] 4. Timeline view (plan 3.6)
  - [ ] 4.1 Date model and formatter (exact, range, approximate, BCE) with property tests. _R3.3_
  - [ ] 4.2 Virtualized timeline list with sticky era headers and scrubber. _R3.1, R3.4, R6.2_
  - [ ] 4.3 Event detail sheet with source badge, "Read article" and "Show on map". _R3.2, R3.5_
  - [ ] 4.4 Filters (era, subject) and empty-after-filter state. _R3.4, R7.1_

- [ ] 5. Linking (plan 3.6)
  - [ ] 5.1 Link bus module and navigation-state restore. _R4.5_
  - [ ] 5.2 Article reader: "On the map" and "On the timeline" actions. _R4.1_
  - [ ] 5.3 Marker sheet "Show events here"; timeline "Show on map"; search result map icon. _R4.2 to R4.4_
  - [ ] 5.4 Property: unknown ids in link-bus calls never crash. _R4_

- [ ] 6. States, accessibility, verification (plan 3.9)
  - [ ] 6.1 States: loading, map failed with fallback, no places in view, empty timeline. _R7.1_
  - [ ] 6.2 Screen reader, keyboard, text scaling, reduced motion, contrast. _R7.2, R7.3_
  - [ ] 6.3 Airplane-mode run on the demo phone; measure budgets and record numbers. _R1.1, R6_

## Done when
On the demo Android phone in airplane mode, the map opens on Liberia with working markers (or the fallback map says why), the timeline lists at least 60
cited events, map and timeline link to each other and to articles, the property-based tests and validator checks pass, and the budgets are met or recorded with a decision (plan 3.6, gate M4).
