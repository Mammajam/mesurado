# Search: design

Implements: requirements.md (R1 to R7). Runs inside the PWA in a dedicated Web Worker.

## Overview
```
UI (main thread) <-- postMessage --> search worker
                                        |- keyword index (MiniSearch-compatible JSON or compact binary)
                                        |- passages store (id, article, heading path, text offsets)
                                        |- embeddings.i8 (int8 matrix, one row per passage)
                                        '- query embedder (ONNX model via WebAssembly), loaded lazily
```
Pipeline: parse query -> keyword rank -> (if hybrid) embed query + cosine rank -> reciprocal rank fusion ->
group, dedupe, cap per article -> attach highlights and normalized score -> return.

## Key decisions
- **Worker boundary.** All indexes live in a worker so typing never blocks. The main thread talks to a small typed API only.
- **Keyword first, always.** Keyword search is the baseline and is available on every device. Semantic search is an
  enhancement behind a capability test, matching the risk plan that Tier 1 ships first.
- **Keyword engine.** Use a small, MIT-licensed library (MiniSearch) or a custom inverted index. Prefer the library for
  prefix and fuzzy support; confirm its index size and load time on the demo phone in the search spike (task 1). Fallback:
  the pipeline's own compact format with a small custom reader.
- **Semantic engine.** `all-MiniLM-L6-v2` (384 dims, Apache-2.0) as an int8 ONNX file, run through ONNX Runtime Web (WASM,
  no WebGPU needed) or transformers.js. Brute-force cosine over int8 vectors: for 20,000 passages at 384 dims the matrix
  is about 7.7 MB and a full scan takes tens of milliseconds, so no ANN index is needed.
- **Fusion.** Reciprocal rank fusion with k = 60: `score(d) = sum 1 / (k + rank_i(d))`. It needs no calibration between
  keyword scores and cosine scores and is deterministic.
- **Normalized relevance for Ask.** Fusion scores are not comparable across queries, so each hit also carries
  `relevance` in [0, 1]: for hybrid, the larger of the passage's cosine similarity and a keyword coverage score (share of
  query terms matched, weighted by term rarity); for keyword-only, the coverage score alone. Ask mode applies its threshold
  to `relevance`. The threshold value is tuned in the Ask spec using the evaluation question set.
- **Deterministic ordering.** Ties break by passage id.
- **No persistence of queries** except an opt-in recent-searches list in local storage that the student can clear.

## Data types
```ts
type Hit = {
  passageId: string;        // "wp:Liberia#007"
  articleId: string;        // "wp:Liberia"
  title: string;
  headingPath: string[];
  excerpt: string;          // passage text trimmed around the best match
  highlights: [number, number][]; // offsets inside excerpt
  score: number;            // fused score, for ordering only
  relevance: number;        // 0..1, for thresholding
  ranks: { keyword?: number; semantic?: number };
};
type SearchOptions = { limit?: number; subject?: string; mode?: "keyword" | "hybrid" };
// worker API
search(query: string, options?: SearchOptions): Promise<Hit[]>;
suggest(prefix: string): Promise<string[]>;
status(): { mode: "keyword" | "hybrid"; ready: boolean; loadedMs: number };
```

## Budgets (confirm on the demo Android phone in task 0.4)
| Measure | Target |
|---|---|
| Keyword query, warm | median under 150 ms, worst under 400 ms |
| Hybrid query, warm | median under 800 ms, worst under 1.5 s (query embedding is the cost) |
| Index load, cold | under 3 s for keyword; semantic model load under 8 s, shown with progress |
| Worker memory | under 150 MB total |
| Semantic model file | about 23 MB int8, counted in the pack's 150 MB budget |

## Capability test and mode choice (R3.4, R6.4)
At first launch the app runs a 1 to 2 second test: load the model if the file is present, embed 5 sample queries, record
median time. If the median is above 1.2 s or loading fails, choose keyword-only. The result and the override live in
settings. Low-power mode or the browser's low-memory signal forces keyword-only for the session.

## UI states
- First load: progress bar with "Preparing offline search".
- Typeahead: suggestions list from `suggest()`.
- Results: grouped by article, highlighted excerpt, heading path, mode badge when keyword-only.
- No results: "No match in this pack" plus related-article suggestions and a hint to try simpler words.
- Error: "Search could not start" with Retry and a link to reinstall the pack.

## Testing strategy
- **Property-based (fast-check):** for any generated pack and query, every hit's `passageId` exists and `highlights` lie
  inside the excerpt; results are identical across repeated runs; no more than 3 hits per article in the top N; an empty
  query returns an empty list; `relevance` is always within [0, 1].
- **Property:** keyword-only mode never loads or calls the embedder.
- **Unit tests:** accent folding, prefix match, one-typo tolerance, stop-word handling, RRF merge on fixed ranks.
- **Evaluation hook:** the evaluation spec records search hit-rate (expected source passage in the top 5) per question.
- **Device test:** run the budget measurements on the demo Android phone and record them in `eval/results/`.

## Risks
- Query embedding on a cheap phone may exceed the budget; mitigated by keyword-only fallback and the automatic mode test.
- Index and model size push the pack over budget; mitigated by measuring in the spike and cutting passages before images.
- Fuzzy matching can surface noisy hits; restrict it to words of five letters or more and rank exact matches first.
- Local place and person names (Liberian English, Kpelle, and other names) may be misspelled; rely on prefix and one-typo
  tolerance, and add alias entries for common variants in the pipeline's selection file.
