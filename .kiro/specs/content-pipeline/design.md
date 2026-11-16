# Content pipeline: design

Implements: requirements.md (R1 to R8). Language: Python 3.12.

## Overview
```
selection.yaml -> select -> fetch (cache) -> clean -> passages -> index + embed -> package -> validate -> pack/
```
Each stage reads the previous stage's output from `pipeline/work/` and is idempotent. `pipeline/build.py` runs them
in order and writes the final pack to a new directory under `pipeline/out/<version>/`, then moves it into place only
if validation passes.

## Layout
```
pipeline/
  selection.yaml        topics grouped by subject
  build.py              entry point: python -m pipeline.build [--subjects history,geography]
  stages/               select.py fetch.py clean.py passages.py index.py package.py
  validate/             shared validator library (also imported by tools/pack-validator)
  cache/                fetched source files (gitignored)
  work/                 intermediate stage output (gitignored)
  out/                  built packs (gitignored; manifest copied to pack/ and committed)
```

## Data formats

### selection.yaml
```yaml
subjects:
  history:   {articles: [{source: wikipedia, title: "Liberia"}, ...]}
  geography: {articles: [...]}
allowed_licenses: [CC-BY-SA-4.0, CC-BY-SA-3.0, CC-BY-4.0, CC0-1.0, PD]
```

### manifest.json (one entry per item)
```json
{"id":"wp:Liberia","type":"article","title":"Liberia","source_url":"https://en.wikipedia.org/wiki/Liberia",
 "revision":"1234567890","license":"CC-BY-SA-4.0","attribution":"Wikipedia contributors",
 "retrieved_at":"2026-11-20","modifications":["cleaned","split into passages"],"subject":"history"}
```
Images have `type: image`, the Commons file page as `source_url`, and the license read from `extmetadata`.

### passages.jsonl
```json
{"id":"wp:Liberia#007","article":"wp:Liberia","heading_path":["History","Colonization"],
 "text":"...","start":10432,"end":11870,"words":212}
```
`start` and `end` are character offsets into the cleaned article text stored in the ZIM, so the reader can highlight.

### Search files
- `keyword.idx`: inverted index over lowercased, accent-folded tokens of passages and titles (format chosen to be loaded by a small JS reader; MiniSearch-compatible JSON or a custom compact binary).
- `embeddings.i8`: row per passage, int8, with a header (model, dims, count) and a scale table.
- `meta.json`: pack version, content hash, model name and license, counts, build date, subjects.
- `map.pmtiles`, `map-style.json`, glyphs, sprites, `fallback-map.svg`, `timeline.json`: map and timeline data (see the map-and-timeline spec).
- `sample-questions.json`: `[{"subject":"history","question":"Who founded Monrovia?","passage":"wp:Monrovia#002"}]`, built from headings and first sentences or a reviewed list.

## Key decisions
- **Python 3.12** for the build: good tooling for text cleaning and embeddings, and `python-libzim` writes ZIM files.
- **Revision pinning** through the MediaWiki API (`oldid`), so a rebuild fetches the same text.
- **Embedding model:** a small open model such as `all-MiniLM-L6-v2` (Apache-2.0, 384 dims), int8-quantized, about 384 bytes per passage. The browser needs the same model to embed a query; the search spec decides whether to run it in WebAssembly or to use keyword-only fallback on weak devices. Record the model license in `meta.json`.
- **Passage size:** 150 to 300 words, split on paragraph boundaries, no overlap. Short sections are merged with their neighbor; very long paragraphs split on sentence boundaries.
- **Ids:** `wp:<Title>` for articles, `<article id>#<three digit index>` for passages. Titles are normalized once and never changed after publication of a pack version.
- **Validator as a library:** `pipeline/validate/` exposes `validate_pack(path) -> Report`. The build, the tests and the MCP server in `tools/pack-validator` all call it.
- **Atomic build:** write to `out/<version>.tmp`, validate, then rename. A failed run leaves the previous pack untouched.

## Budgets (target, confirm on the demo Android phone in task 0.4)
| Item | Target |
|---|---|
| Articles | 1,500 to 3,000 (pack v1 history + geography about 1,000 to 1,500) |
| Total pack | at most 150 MB; text and indexes at most 40 MB |
| Images | WebP, max 800 px wide, about 40 KB average |
| Keyword + embedding load | under 2 seconds on the demo phone |
| Full build | under 20 minutes from a warm cache |

## Validation checks (R6)
1. Every manifest entry has all required fields and an allowed SPDX license.
2. Every file in the ZIM and pack directory has a manifest entry, and vice versa.
3. Every passage's article exists; `text` equals `article_text[start:end]`.
4. Every embedding row maps to a passage id, counts match.
5. No file or text contains "Encarta" (case-insensitive).
6. The pack metadata hash matches the files.
7. Every sample question links to an existing passage id.
8. Every timeline event has a resolvable passage, a valid date or range, and (if it names a place) a place with coordinates.
9. Map datasets and fonts have manifest entries with allowed licenses (Natural Earth public domain, OSM ODbL with attribution, OFL fonts).

## Testing strategy
- **Property-based (Hypothesis):** for any generated article text, passages concatenated by offsets reproduce the cleaned text and each is within size bounds; for any generated manifest, `validate` fails exactly when a required field is missing or the license is not allowed; passage ids are stable under unchanged text.
- **Unit tests:** cleaning rules on saved Wikipedia HTML fixtures; license parsing from Commons metadata fixtures.
- **Integration:** build a 5-article fixture pack end to end in under a minute; then corrupt it (remove a license, break an offset) and confirm the validator fails.
- Tests run in CI and from the hook that fires on pack change.

## Risks
- Wikipedia HTML varies widely; cleaning needs fixtures from real pages across history and geography.
- Commons image licenses are per file and sometimes unclear; the rule is to exclude when unsure.
- Pack size on a phone: image count and size are the main lever; tune after the first full pack.
- Share-alike: the pack as a whole is CC BY-SA, recorded in CONTENT-LICENSE.md and the in-app attribution screen.
