# Search: tasks

Each task names the requirements it satisfies and the plan task it advances. Commit with the plan id.

- [ ] 1. Spike on the demo Android phone (plan 0.4, 3.3)
  - [ ] 1.1 Compare MiniSearch and a custom inverted index on a 1,000-article test set: index size, load time, query time. Record in `eval/results/search-spike.md`. _R2, R6_
  - [ ] 1.2 Measure the int8 MiniLM ONNX model through ONNX Runtime Web (WASM): load time and per-query embedding time. Decide whether hybrid is viable on the phone. _R3, R6_

- [ ] 2. Worker and keyword search (plan 3.3)
  - [ ] 2.1 Create the search worker with typed message API: `search`, `suggest`, `status`, cancel on newer query. _R5, R6.3_
  - [ ] 2.2 Load the keyword index and passage store from the pack; progress reporting. _R6.1_
  - [ ] 2.3 Implement accent folding, prefix on last word, one-typo tolerance, title boost, phrase boost, stop words. _R2_
  - [ ] 2.4 Highlights and excerpt trimming. _R1.2, R5.2_
  - [ ] 2.5 Property-based tests: hits resolve, highlights in range, determinism, per-article cap, empty query. _R4, R5_

- [ ] 3. Semantic search and fusion (plan 3.3)
  - [ ] 3.1 Load the embedding model lazily; check model name and version against `meta.json`. _R3.2_
  - [ ] 3.2 Embed the query and score all passages by cosine on the int8 matrix. _R3.1_
  - [ ] 3.3 Reciprocal rank fusion, dedupe, `relevance` score definition. _R4_
  - [ ] 3.4 Fallback to keyword-only on load failure or slow response, with a mode notice. _R3.3_
  - [ ] 3.5 Capability test at first launch, settings override, low-power rule. _R3.4, R6.4_
  - [ ] 3.6 Property: keyword-only mode never calls the embedder; `relevance` in [0, 1]. _R4.2_

- [ ] 4. Search interface (plan 3.3)
  - [ ] 4.1 Search input with typeahead from `suggest`. _R5.3_
  - [ ] 4.2 Results screen grouped by article with highlights and heading path; open article at the passage. _R1.2, R1.3_
  - [ ] 4.3 States: first load, no results, error with retry, keyword-only badge. _R7.1_
  - [ ] 4.4 Accessibility: keyboard, screen reader labels, text scaling, contrast. _R7.2_
  - [ ] 4.5 Optional recent searches, local only, with a clear button. _R7.4_

- [ ] 5. Verification
  - [ ] 5.1 Airplane-mode test on the demo phone: first query works after install with no network. _R1.4, R7.3_
  - [ ] 5.2 Measure latency and memory against the budgets; record in `eval/results/`. _R6_
  - [ ] 5.3 Expose search hit-rate to the evaluation harness (expected passage in top 5). _evaluation spec_

## Done when
Search returns correct, resolvable, highlighted hits offline on the demo Android phone within the budgets, keyword-only mode works
on its own, hybrid is used when the phone can run it, and the property-based tests pass (plan tasks 3.3 and gate M2).
