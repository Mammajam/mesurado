# Evaluation: design

Implements: requirements.md (R1 to R7).

## Overview
```
eval/questions.yaml --preflight--> resolve quotes to passages in the pack
        |
        v
 harness (Node + Playwright) --loads--> the real app modules (search worker, Ask) in Chrome
        |                                  |-- desktop run: headless Chrome, network allowed or blocked
        |                                  '-- device run: /bench page on the demo phone, exports JSON
        v
 scorer (rules) -> metrics + Wilson intervals -> eval/results/<date>-<packhash>-<device>.{json,md}
        '-> manual sample sheet (eval/results/manual-sample.csv) -> expert marks -> merged into the report
```

## Layout
```
eval/
  questions.yaml          the question set (versioned)
  splits.json             dev/test ids from a recorded seed
  harness/                run.ts, preflight.ts, score.ts, report.ts, sweep.ts
  bench/                  bench page source (shared with the app build, enabled by ?bench=1)
  results/                reports, sweeps, device logs, manual samples
```

## Question format
```yaml
- id: h-014
  kind: in-pack            # in-pack | out-of-pack | sensitive
  subject: history
  difficulty: medium
  paraphrased: true
  question: "Why did freed people from America settle on the coast of West Africa?"
  expected:                # in-pack only
    article: "wp:American_Colonization_Society"
    quote: "to resettle free African Americans"      # exact phrase inside the expected passage
  key_phrases: ["resettle", "freed", "free African Americans"]   # any one must appear in the answer
  note: "near-miss variant of h-013"
- id: o-007
  kind: out-of-pack
  question: "Who won the 2022 football World Cup?"
  reason: "after the pack's sources"
```
`quote` is resolved to a passage at run time by exact search in the article's passages. If the pack is rechunked, questions still resolve. If the quote
is missing, preflight fails with the question id.

## Metrics and scoring rules
| Measure | Population | Rule |
|---|---|---|
| Retrieval hit@1, hit@5 | in-pack | expected passage id in the first 1 / 5 hits of `search()` |
| Answer accuracy | in-pack | card shown, an extract is from the expected passage, and extract text contains at least one `key_phrase` (case-insensitive) |
| Citation resolution | all shown extracts | passage exists and `passage.text.includes(extract.text)`; must be 100% |
| Citation support (manual) | sample of 30 answers | expert marks yes/no: does the cited passage answer the question |
| Correct refusal | out-of-pack | result kind is refusal |
| False-answer rate | out-of-pack | result kind is answer (100% minus correct refusal) |
| Over-refusal | in-pack | result kind is refusal |
| Sensitive-topic note | sensitive | answer card carries the professional note |
| Latency | all | time from submit to first result and to final card, median, p95, max |
| Offline proof | demo flow | zero network requests and all steps pass with the network blocked |

All rates are reported as `k/n` with a 95% Wilson interval, for example `46/55 = 83.6% (71.7% to 91.1%)`. With sets this small, the intervals
are wide, and the report says so.

## Dev/test split
`splits.json` records the seed and the ids in each half, stratified by kind and subject so both halves have in-pack and out-of-pack questions.
The harness refuses to run a sweep on the test split and records which split each reported number came from. The threshold sweep (dev split) runs per search mode and
writes a table of threshold, answer rate, false-answer rate and over-refusal; the chosen row is written into `ask.json` before the test run.

## Device run
- The app build includes a `/bench` route (enabled only with `?bench=1`) that loads the question set, runs each question through the real search and Ask code,
  records timings with `performance.now()` and outputs, and exports a JSON file through a download or a `fetch` to the dev laptop on the same Wi-Fi **only
  before airplane mode is turned on**; for the offline proof the final run saves JSON to local storage and exports after.
- For airplane-mode proof the phone is put in airplane mode, `/bench` runs the full set and the demo flow, and the network request log (from the service worker) shows zero requests.
- The desktop run uses Playwright with `context.setOffline(true)` and request interception to assert zero requests.

## Report format (Markdown, generated)
Header (commit, pack hash, config versions, device, browser, date, mode), counts of articles, passages, questions and events, validator result, then the metric table with intervals,
the latency table, the threshold choices and sweep run id, the property-test summary, failure types found in the sample, and a limits section. The same numbers are written
to JSON for the Devpost text and write-up.

## Property-based test suite
Collected under `tests/properties/` (fast-check for the app, Hypothesis for the pipeline). Each file's header lists the spec requirement checked. The suite and its case counts are
summarized in the report (Kiro write-up evidence). Properties are defined in their feature specs; this spec owns the suite's runner and the summary.

## Hooks
- `.kiro/hooks/on-pack-change.json`: on change to `pipeline/out/**`, `pack/manifest.json` or `app/config/ask.json`: run validator, run desktop evaluation, write `eval/results/latest.md`.
- `.kiro/hooks/on-spec-change.json`: on change to `.kiro/specs/**`: regenerate `docs/test-checklist.md` listing each requirement and its tests.

## Budgets
| Item | Target |
|---|---|
| Desktop evaluation, pack v1 | under 5 minutes |
| Device run of the full question set | under 10 minutes |
| Report generation | under 10 seconds |

## Risks
- **Small samples:** intervals are wide; report them and avoid claiming more than the data supports.
- **Overfitting to the dev split:** the test split stays untouched until the final run; the harness refuses to tune on it.
- **Questions too easy or too similar to passages:** the paraphrase requirement and near-miss out-of-pack questions mitigate this; the expert's review checks it.
- **Question writing time:** 150 questions is a lot on a 2 to 4 hour day. Write them in batches from the first passages (plan 4.1 starts Nov 22) and keep the reduced target (60 in-pack, 25 out-of-pack) as the recorded fallback.
- **Device runs are manual and slow:** use the bench page and a script that prints the phone steps; do one early dry run before the final one.
- **A number looks bad:** it still gets reported; the plan's honesty rule is that an honest low number is more credible than an unverified high one.
