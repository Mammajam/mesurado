# Map and timeline: design

Implements: requirements.md (R1 to R7). Runs in the PWA on a low-end Android phone (Chrome).

## Overview
```
pack/ map.pmtiles + style + glyphs + sprites     pack/ timeline.json (events)     manifest (coordinates per place article)
        |                                                  |                              |
   MapView (MapLibre GL JS)  or  FallbackMap (SVG)    TimelineView (virtualized list)   place index
        '--------------- shared "link bus": showOnMap(placeId) / showEvents(placeId) / openArticle(passageId) ---------------'
```
The two views know nothing about each other except through the link bus and the data files, so either can be cut or
replaced without breaking the other (plan cut line: map and timeline are cut last).

## Map
### Data
- **Base map source (decision, spike confirms on the phone):**
  - West Africa overview (zoom 0 to 7): Natural Earth (public domain) for countries, coastlines, rivers, lakes, populated places.
  - Liberia detail (zoom 8 to 12): OpenStreetMap extract of Liberia (ODbL), cut with tilemaker or Planetiler into vector tiles with a
    minimal schema (roads, settlements, water, land use, place names).
  - Output: one `map.pmtiles` file read through HTTP-range-style reads from the service worker cache or the local pack file.
- **Budget:** map pack at most 40 MB (overview about 3 to 6 MB; Liberia detail about 20 to 30 MB; glyphs and sprites about 2 MB).
- **Style and fonts:** a minimal style written for this project; glyph files from an OFL-licensed font; license recorded in the manifest and `docs/third-party.md`.
- **Attribution:** "Map data: Natural Earth; OpenStreetMap contributors (ODbL)" shown on the map and on the attribution screen.
- **Borders:** Natural Earth modern boundaries only; names in English; no claims on disputed areas (neutral rendering).

### Renderer
- **Primary:** MapLibre GL JS (BSD-3) with the `pmtiles` protocol plugin; vector tiles keep size small and let us style for contrast.
- **Fallback:** SVG map generated at build time from simplified Natural Earth GeoJSON (West Africa and Liberia counties), with the same markers;
  used when WebGL is missing, MapLibre fails to start within 5 seconds, low-power mode is on, or the student picks "simple map" in settings.
- Both implement the same `MapView` interface: `setMarkers`, `flyTo`, `selectMarker`, `onMarkerTap`, `getViewport`, `setViewport`.

### Markers
- Place articles come from the manifest's `coordinates` (latitude, longitude, precision) filled by the pipeline from Wikipedia/Wikidata coordinates.
- Clustering with a small grid-based algorithm (supercluster, ISC) in a worker; at most 300 markers drawn at once.
- A marker list view (sorted by distance from map center) is the non-gesture alternative.

## Timeline
### Data: `timeline.json` (built from a reviewed source file `pipeline/timeline.yaml`)
```json
{"id":"ev-1822-monrovia","era":"colonization","start":1822,"end":null,"approx":false,
 "title":"Settlers land at Cape Mesurado","summary":"...","summaryType":"copied|summary",
 "passage":"wp:Monrovia#002","article":"wp:Monrovia","place":"wp:Monrovia","subject":"history"}
```
- **Dates:** integers with negative years for BCE; `approx` for "about"; `end` for ranges; display strings derived by one date formatter with tests.
- **Eras:** named list in `timeline.yaml` (for example Early states and trade; Atlantic trade; Settlement and colonization; Independence and the republic; Conflict and recovery; Contemporary).
- **Source of events:** hand-curated by the builder, each tied to a passage in the pack; a Wikidata date can be a cross-check but is not copied wholesale.
- **Count:** at least 60 events in pack v1, about 8 to 12 per era; reviewed by the subject expert.

### UI
- Vertical list with sticky era headers, a decade/century scrubber on the right edge, filters in a bottom sheet (era, subject).
- Each row: date badge, title, summary, source badge; tap opens a detail sheet with "Read article" and "Show on map".
- Virtualized list so scrolling stays smooth with several hundred rows later.

## Link bus
A tiny typed event module (no network, no global state beyond router): `showOnMap(placeId)`, `showEventsForPlace(placeId)`,
`openArticle(articleId, passageId)`, `openTimeline(eventId)`. Navigation state (map viewport, timeline scroll and filters) is stored in memory and the history state so back/forward restore it.

## Budgets (confirm on the demo Android phone in task 0.4)
| Measure | Target |
|---|---|
| Map first open (warm) | under 3 s |
| Pan frame rate | at least 24 fps |
| Map pack size | at most 40 MB |
| Fallback map size | at most 400 KB |
| Timeline first render | under 500 ms |
| Memory (map + timeline open) | under 200 MB |

## Testing strategy
- **Property-based (fast-check):**
  - for any generated event set, the timeline is sorted by start date and every event's passage id exists;
  - date formatting round-trips for exact, range, approximate and BCE dates;
  - clustering never loses a marker (the sum of cluster counts equals the number of markers) at any zoom;
  - for any viewport, every returned marker lies inside it; link-bus calls with unknown ids never crash and show an error state.
- **Validator checks (pipeline):** each event has a resolvable passage, a valid date or range, and coordinates for its place.
- **Unit tests:** era grouping, scrubber mapping, summary-type labels.
- **Device tests:** map first open, frame rate, memory and the WebGL-off fallback on the demo Android phone; record numbers in `eval/results/`.
- **Subject expert review** of the events list and the era names.

## Risks
- MapLibre (WebGL) may be heavy on a budget Android phone: mitigated by the spike, the 5-second start check and the SVG fallback.
- Map pack size pushes the whole pack over budget: lower the Liberia detail zoom (to z10) before cutting images.
- OSM data adds ODbL obligations: attribution is shown and recorded; the pack is already CC BY-SA, so license notes explain both.
- Event curation is slow work: cap pack v1 at 60 events and write them from passages already in the pack.
- Sensitive history (conflict, slavery, colonization): neutral language, expert review, every event cited.
