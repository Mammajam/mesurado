# Ask mode: tasks

Each task names the requirements it satisfies and the plan task it advances. Commit with the plan id.

- [ ] 1. Core types and the citation gate first (plan 3.4, 4.3)
  - [ ] 1.1 Define `AnswerCard`, `Refusal`, `Extract`, `AskConfig` and the `Answerer` interface. _R2, R7_
  - [ ] 1.2 Implement `getPassage(id)` over the pack's passage store and the citation resolver as a pure function: passage exists and the full passage text includes the extract exactly. _R3.1 to R3.3_
  - [ ] 1.3 Property-based tests for the resolver (substring check, altered text rejected, empty result becomes Refusal). _R3_

- [ ] 2. Retrieval and refusal (plan 3.4)
  - [ ] 2.1 Question normalization and the search call using the search worker. _R1_
  - [ ] 2.2 Threshold gate with per-mode thresholds and `relatedFloor`; Refusal with related articles; `app/config/ask.json` with starting values. _R3.4, R3.5, R5.1_
  - [ ] 2.3 Property: any question whose best `relevance` is below the threshold always yields a Refusal. _R3.4_

- [ ] 3. Extract selection and sensitive topics (plan 3.4)
  - [ ] 3.1 Sentence splitter with fixtures (abbreviations, decimals, quotes). _R2.1_
  - [ ] 3.2 Sentence scoring by weighted term overlap; optional semantic boost limited to the top 3 passages and skipped over `sentenceEmbedBudgetMs`; extracts cut by character offsets so whitespace is preserved; pick up to 3, one per passage. _R2.1, R2.2_
  - [ ] 3.3 `app/config/sensitive.json` whole-word and phrase lists; match only with a subject-tag agreement or a second term; fixed professional-advice note; tests for false triggers such as "river bank". _R4_
  - [ ] 3.4 Determinism and instruction-injection tests (question text cannot change behavior). _R1.4, R5.2_

- [ ] 4. Interface (plan 3.4, 3.9)
  - [ ] 4.1 Ask screen with input, example questions read from the pack's sample-question file, and loading state. _R6.1, R6.2_
  - [ ] 4.2 Answer card: quotes, source lines, license badge, open-in-article link, show-full-passage toggle. _R2.2, R2.3_
  - [ ] 4.3 Refusal view, search-error view with retry, keyword-only badge. _R6.2_
  - [ ] 4.4 Accessibility and small-screen checks on the demo Android phone; recent questions with clear button. _R6.3, R6.4_

- [ ] 5. Threshold tuning with the evaluation set (plan 4.2, 4.4)
  - [ ] 5.1 Run the evaluation harness across threshold values separately for keyword-only and hybrid mode; plot answer rate versus false-answer rate for each. _R5.3_
  - [ ] 5.2 Choose both thresholds and `relatedFloor`, write them to `ask.json` with the run id, and record the trade-offs in `eval/results/`. _R5.1, R5.3_
  - [ ] 5.3 Have the subject expert review a sample of answers and refusals; record findings. _R5.3_

- [ ] 6. Verification
  - [ ] 6.1 Airplane-mode run on the demo Android phone: answer, refusal and sensitive-topic cases. _R1.3_
  - [ ] 6.2 Measure latency against the budgets and record the numbers. _R1.1_

## Done when
On the demo Android phone in airplane mode, an in-pack question shows verbatim extracts with working citations, an out-of-pack question is refused with related
articles, a sensitive-topic question carries the professional note, the resolver and refusal properties pass, and the threshold is chosen from the evaluation data (plan 3.4, 4.3, gate M3).
