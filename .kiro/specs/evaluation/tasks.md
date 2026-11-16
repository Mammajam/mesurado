# Evaluation: tasks

Each task names the requirements it satisfies and the plan task it advances. Commit with the plan id.
Never-cut items (plan): 4.1, 4.2, 4.4. The property suite (4.3) is the main Kiro-depth evidence; keep at least the three core properties if time is short.

- [ ] 1. Question set (plan 4.1)
  - [ ] 1.1 Define the question schema and the preflight that resolves quotes to passages. _R1.2, R1.7_
  - [ ] 1.2 Write in-pack questions from the first passages: target 100 (fallback 60), at least a third paraphrased. _R1.1, R1.3_
  - [ ] 1.3 Write out-of-pack questions (target 40, fallback 25): near misses, off-topic, after-the-sources. _R1.4_
  - [ ] 1.4 Write 10 sensitive-topic questions (money, health, legal). _R1.1_
  - [ ] 1.5 Create `splits.json` from a recorded seed, stratified by kind and subject. _R1.5_
  - [ ] 1.6 Subject expert reviews at least 40 questions and their expected sources; record the result. _R1.6_

- [ ] 2. Harness core (plan 4.2)
  - [ ] 2.1 `run.ts`: load the real app modules in headless Chrome with Playwright; run questions through search and Ask. _R3.1, R3.2_
  - [ ] 2.2 `score.ts`: retrieval, answer accuracy, citation resolution, refusal, sensitive-note scoring; Wilson intervals. _R2.1 to R2.5, R2.9_
  - [ ] 2.3 `report.ts`: JSON and Markdown outputs with commit, pack hash, config versions, device and browser. _R3.1, R3.4_
  - [ ] 2.4 Guards: fail on missing source, validator failure, tuning on the test split. _R3.6, R4.2_
  - [ ] 2.5 Determinism test: two runs give identical accuracy numbers. _R3.5_
  - [ ] 2.6 One command (`npm run eval`) prints the full report; time it against the 5-minute budget. _R3.1, R6.3_

- [ ] 3. Threshold sweep (plan 4.2, feeds Ask spec task 5)
  - [ ] 3.1 `sweep.ts`: dev split across thresholds, per search mode; table of answer, false-answer and over-refusal rates. _R4.1_
  - [ ] 3.2 Write chosen thresholds into `ask.json` with the sweep run id; record the trade-off. _R4.2_

- [ ] 4. Latency and offline proof (plan 4.2, 4.4)
  - [ ] 4.1 `/bench` page (`?bench=1`) that runs the question set and the demo flow and records timings. _R3.3, R2.6_
  - [ ] 4.2 Offline proof: Playwright offline context with request interception; zero requests asserted. _R2.7_
  - [ ] 4.3 Device-run script and checklist for the demo phone (airplane mode, export, screenshots). _R7.1, R7.2_
  - [ ] 4.4 One early dry run on the phone to find problems before the final run. _R7_

- [ ] 5. Property-based test suite (plan 4.3)
  - [ ] 5.1 Collect properties from the feature specs under `tests/properties/` with spec-requirement comments. _R5.1, R5.3_
  - [ ] 5.2 Runner and summary (property count, generated cases) included in the report. _R5.2_
  - [ ] 5.3 Core three first: citation resolution, refusal below threshold, license record completeness. _R5.1_

- [ ] 6. Automation (plan 1.4)
  - [ ] 6.1 Kiro hook: on pack or `ask.json` change run validator and desktop evaluation; write `eval/results/latest.md`. _R6.1_
  - [ ] 6.2 Kiro hook: on spec change regenerate `docs/test-checklist.md`. _R6.2_
  - [ ] 6.3 Each hook fires once in a test run (plan 1.4 done-when). _R6_

- [ ] 7. Final run (plan 4.4)
  - [ ] 7.1 Freeze tag, final pack, test split, on the demo Android phone with the network disabled. _R7.1_
  - [ ] 7.2 Manual samples: expert marks citation support (30 answers) and failure types. _R2.4, R4.3_
  - [ ] 7.3 Commit the results file whatever the numbers are; copy numbers from it into the write-up, video notes and Devpost text. _R7.3_

## Done when
One command prints the full report on the desktop; the demo phone run in airplane mode records latency, accuracy, refusal quality and offline proof; the results file is committed with commit hash, pack hash and
intervals; the property suite passes and is summarized; both hooks fire; and every number in the write-up is traceable to that file (plan 4.1 to 4.4, gates M3 and M5).
