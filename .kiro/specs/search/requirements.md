# Search: requirements

Plan tasks: 3.3 (search interface), 2.3 (index inputs). Consumers: article reader, Ask mode, quizzes, map and timeline.
Depends on: content-pipeline spec (passages.jsonl, keyword index, int8 embeddings, meta.json).
Steering: product, tech, cite-or-refuse.

## Introduction
Search finds articles and passages in the on-device pack, with no network, on a low-end Android phone running Chrome.
It combines keyword matching and meaning-based (semantic) matching, and it is the retrieval layer that Ask mode relies
on, so it must return passage ids that always resolve and a score that Ask can threshold.

Glossary
- **Hit**: one search result: a passage id, its article, score, highlight ranges and heading path.
- **Hybrid search**: keyword ranking and semantic ranking merged into one list.
- **Search worker**: a Web Worker that holds the indexes and runs queries off the main thread.
- **Tier 1 device**: a device where the semantic model is not loaded; keyword search only.

## Requirements

### R1. Query and results
**User story:** As a student, I want to type a topic and see the most relevant articles and passages so that I can open what I need.
1. WHEN the student submits a query, THE search worker SHALL return ranked hits from the pack within the latency budgets in design.md.
2. THE results screen SHALL group hits by article, show the article title, the best passage excerpt with matched words highlighted, and the heading path.
3. WHEN the student opens a hit, THE app SHALL open the article scrolled to and highlighting that passage.
4. THE search SHALL work entirely offline, including the first query after install.
5. IF the query is empty or only whitespace, THEN THE search SHALL return no hits and SHALL NOT show an error.

### R2. Keyword search
1. THE keyword search SHALL match on lowercased, accent-folded tokens of passages and article titles.
2. THE keyword search SHALL support prefix matching for the last typed word, so results appear while typing.
3. THE keyword search SHALL tolerate one-character typos for words of five letters or more.
4. THE keyword search SHALL boost title matches over body matches and exact phrases over scattered words.
5. THE keyword search SHALL ignore a fixed list of common English stop words when ranking, but SHALL still match a query made only of stop words.

### R3. Semantic search
1. WHERE the device can run the embedding model, THE search SHALL embed the query on-device and rank passages by cosine similarity against the pack's int8 embeddings.
2. THE semantic search SHALL use the same model name and version recorded in the pack's `meta.json`, and SHALL refuse to run if they differ.
3. IF the embedding model fails to load or is too slow, THEN THE search SHALL fall back to keyword-only results and SHALL tell the student the mode in use.
4. THE app SHALL pick keyword-only or hybrid automatically at first launch from a short capability and speed test, and SHALL allow the student to change it in settings.

### R4. Hybrid ranking
1. WHEN both rankings are available, THE search SHALL merge them with reciprocal rank fusion, so no score calibration between them is needed.
2. THE search SHALL return, for each hit, a normalized relevance score between 0 and 1 and the ranks from each method, for use by Ask mode.
3. THE search SHALL be deterministic: the same query and pack SHALL return the same ordered hits.
4. THE search SHALL remove duplicate hits and SHALL return at most 3 passages per article in the top results.

### R5. Interface for Ask mode and other features
1. THE search worker SHALL expose one function, `search(query, options) -> Hit[]`, with options for result limit, subject filter and mode (keyword, hybrid).
2. EVERY hit's passage id SHALL exist in the pack, and its highlight ranges SHALL lie within the passage text.
3. THE search worker SHALL expose `suggest(prefix) -> string[]` returning up to 8 article titles and common terms for typeahead.
   - THE search worker SHALL expose `getPassage(id)` returning the full passage text and offsets, or null if the id is unknown, so that Ask mode can verify citations against full text.
   - EVERY hit SHALL carry the article's license id read from the pack manifest.
4. THE search SHALL expose the threshold-relevant score so that Ask mode can refuse when no hit is relevant enough (see cite-or-refuse).

### R6. Performance and device limits
1. THE index SHALL load in a Web Worker without blocking the interface, with a visible progress state on first load.
2. THE search SHALL keep memory use within the budget in design.md on the demo Android phone.
3. THE search SHALL cancel an in-flight query when a newer one is submitted.
4. WHEN the device is in low-power or low-memory mode, THE search SHALL use keyword-only mode and SHALL show that it did.

### R7. States and accessibility
1. THE search screen SHALL have designed states: first-load progress, no results (with suggestions to broaden), index error with a retry, and keyword-only mode notice.
2. THE search input and results SHALL be usable by keyboard and screen reader, support text scaling, and meet contrast guidelines.
3. THE search SHALL send no network requests and SHALL NOT store or transmit the student's queries beyond the current session.
4. WHERE the student has opened recent searches, THE app SHALL keep them only on the device and SHALL let the student clear them.

## Out of scope
Voice search, query-by-image, cross-language search, search across other devices, personalization or logging of queries.
