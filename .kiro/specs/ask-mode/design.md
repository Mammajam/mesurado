# Ask mode: design

Implements: requirements.md (R1 to R7). Runs in the PWA; uses the search worker.

## Overview
```
question -> normalize -> search(question, limit 8) -> threshold check -> extract selection
         -> citation resolver (hard gate) -> sensitive-topic note -> answer card | refusal
```
Every step is plain code. There is no model in the loop, so there is no way to produce text outside the pack.

## Components
- **normalize:** trims, collapses whitespace, strips leading question words ("what is", "who was", "when did") only for
  the search query; the original text is kept for display.
- **search call:** `search(query, {limit: 8, mode: auto})` from the search spec; returns hits with `relevance`, `passageId`, `license` and the active `mode`.
- **passage access:** the resolver and sentence selector read the FULL passage text from the pack's passage store by id (`getPassage(id)`); they never rely on the trimmed `excerpt` in a hit.
- **threshold gate:** if `hits[0].relevance < config.threshold[mode]`, return a Refusal. Related articles come from the same hits whose `relevance` is at least `config.relatedFloor`, so a refusal can still show something useful when any hit is reasonably close.
- **extract selection:** for the top 3 passages above threshold, split the passage into sentences, score each sentence
  against the question, and select the best sentence plus its neighbour if the score is close.
  - Scoring: weighted term overlap with the query terms (rare terms weigh more); this is the default and works on its own.
  - Optional semantic boost: only in hybrid mode and only for the sentences of the top 3 passages (about 30 sentences), embed them at query time and add the cosine to the overlap score. Skip it if the first query-time embedding exceeds `config.sentenceEmbedBudgetMs`.
  - Select at most 3 extracts across the answer, at most one per passage, ordered by relevance.
- **citation resolver (the gate):** for each extract, check that `passageId` exists in the pack and that
  `getPassage(passageId).text.includes(extract.text)` (exact match including whitespace). Drop failures. If zero remain, return the Refusal. This function is pure,
  has no dependency on search quality, and is the one place the cite-or-refuse rule is enforced.
- **sensitive-topic note:** match whole words and listed phrases from `app/config/sensitive.json` (money, health, legal) in the question and passages. A match counts only when the article's subject tag agrees or a second listed term appears in the same passage, which avoids false triggers such as "river bank". If matched, attach the fixed professional-advice note.
- **Answerer interface:** `answer(question, hits, config) -> AnswerCard | Refusal`. `ExtractiveAnswerer` is the only
  implementation. A future `GenerativeAnswerer` would return the same type and be run through the same resolver.

## Data types
```ts
type Extract = { text: string; passageId: string; articleId: string; title: string; headingPath: string[];
                 license: string; start: number; end: number };           // offsets inside the passage
type AnswerCard = { kind: "answer"; question: string; extracts: Extract[]; passagesUsed: number;
                    sensitiveNote?: string; mode: "keyword" | "hybrid" };
type Refusal   = { kind: "refusal"; question: string; related: { articleId: string; title: string }[]; reason: "below-threshold" | "no-hits" | "unresolved" };
type AskConfig = { threshold: { keyword: number; hybrid: number }; relatedFloor: number; maxExtracts: 3; maxPassages: 3;
                   sentenceScoreMin: number; sentenceEmbedBudgetMs: number; version: string };
```
`AskConfig` lives in `app/config/ask.json` with a `version`; the release records each threshold and the evaluation run that chose it. Keyword-only and hybrid relevance scores are distributed differently, so each mode has its own threshold.

## Display
- Answer card: restated question, extract quotes with a left rule, each with a source line (title, heading path, license
  badge, "Open in article"), "Show full passage" toggle, optional professional-advice note, mode badge when keyword-only.
- Refusal: "The pack does not cover this question." plus related articles and "Search these words".
- Empty state: example questions generated from pack passages (stored in the pack so no model is needed).

## Budgets (confirm on the demo Android phone)
| Measure | Target |
|---|---|
| Question to answer card, keyword-only | median under 400 ms, worst under 900 ms |
| Question to answer card, hybrid | median under 1.2 s, worst under 2 s |
| Answer card render | under 100 ms |

## Testing strategy
- **Property-based (fast-check):**
  - for any pack and question, every displayed extract's `passageId` exists and the extract is a substring of that passage;
  - for any pack and any question whose best `relevance` is below the threshold, the result is always a Refusal;
  - for any question, the same pack and config produce identical output (determinism);
  - the resolver never lets an extract through whose text was altered by even one character;
  - question text containing instruction-like strings produces the same kind of output as any other text.
- **Unit tests:** sentence splitting on abbreviations and decimals, question-word stripping, sensitive-topic matching, refusal contents.
- **Evaluation spec tie-in:** answer accuracy, citation faithfulness, refusal quality and latency are measured by the harness on
  the question set; the threshold is chosen from that data (task 4 of this spec).
- **Manual check:** a sample of answers reviewed by the subject expert.

## Risks
- A single best sentence can be correct but lack context: mitigated by "Show full passage" and showing the neighbouring sentence.
- Threshold too high refuses valid questions; too low answers out-of-pack ones. Each mode's threshold is chosen from its own evaluation curve, and reported with both rates.
- Extractive answers feel less like a tutor than generated ones; this is a deliberate trade for trust and offline reliability, and the Answerer interface keeps the generative option open.
- Sentence splitting errors on abbreviations; mitigated by unit tests with real passage fixtures. Extracts are cut by character offsets from the passage, never re-joined from tokens, so whitespace is preserved.
- Latency budgets are estimates until measured on the demo phone.
