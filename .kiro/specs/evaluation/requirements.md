# Evaluation: requirements

Plan tasks: 4.1 (question set), 4.2 (harness), 4.3 (property-based tests), 4.4 (final run on the demo device).
Depends on: content-pipeline (pack, passage ids), search (hits, `relevance`), Ask mode (answers, refusals, thresholds), quizzes (bank stats).
Steering: cite-or-refuse, license-record, product.

## Introduction
The evaluation produces the one measured result the pitch needs and proves the product works offline. It checks that Ask answers from the right
passage, that every citation resolves, that out-of-pack questions are refused, that the app is fast enough on a low-end Android phone, and that the whole
demo flow works with the network blocked. The numbers are reported as measured, with sample sizes and uncertainty, whatever they turn out to be.

Glossary
- **Question set**: the committed list of test questions with expected sources (`eval/questions.yaml`).
- **In-pack question**: a question the pack can answer; has an expected source.
- **Out-of-pack question**: a question the pack cannot answer; the correct result is a refusal.
- **Dev split / test split**: two disjoint halves of the question set; the dev split is used to tune thresholds, the test split is used only for the reported numbers.
- **Run**: one execution of the harness against one pack, one build and one device, producing a report.
- **Demo device**: the Android phone used for the final run and the video.

## Requirements

### R1. Question set
**User story:** As a judge, I want to rerun the same questions against the project so that I can trust the numbers.
1. THE question set SHALL contain at least 100 in-pack questions, 40 out-of-pack questions and 10 sensitive-topic questions for pack v1, each with an id, subject and difficulty.
2. EACH in-pack question SHALL name its expected source as an article id and a quote (a short exact phrase from the expected passage), and a list of key phrases that a correct answer must contain, so that the set survives rechunking of the pack.
3. THE questions SHALL be written from the pack's own passages and phrased in the students' own words, with at least a third of them sharing few words with the passage (paraphrased), so that keyword overlap alone does not solve them.
4. THE out-of-pack questions SHALL include near misses (same subject, topic not covered), off-topic questions, and questions about events after the pack's sources.
5. THE set SHALL be split into dev and test halves, fixed by a recorded seed; the dev half is used for threshold tuning, and the test half SHALL NOT be used for tuning.
6. THE subject expert SHALL review a sample of at least 40 questions and their expected sources before the final run, and the result SHALL be recorded.
7. THE set SHALL be committed to the repo with a version and SHALL be validated by a preflight check that every expected quote still resolves to a passage in the pack under test.

### R2. Measures
1. THE harness SHALL measure **retrieval**: the share of in-pack questions whose expected passage is in the top 1 and the top 5 search hits.
2. THE harness SHALL measure **answer accuracy**: the share of in-pack questions where the answer card cites the expected source and contains at least one required key phrase; scored pass or fail by rule, with a manual sample for confirmation.
3. THE harness SHALL measure **citation resolution**: the share of displayed extracts whose passage exists and that appear exactly in it; THE target SHALL be 100%, and any failure SHALL be reported as a defect.
4. THE harness SHALL measure **citation support**: for a manual sample of at least 30 answers, whether the cited passage actually supports the extract as an answer to the question.
5. THE harness SHALL measure **refusal quality**: the share of out-of-pack questions refused (correct refusal), the share answered (false-answer rate), and the share of in-pack questions wrongly refused (over-refusal rate).
6. THE harness SHALL measure **latency** on the demo device: time to first result and time to full answer, with median, 95th percentile and worst case, for keyword-only and hybrid modes where both exist.
7. THE harness SHALL measure **offline proof**: the full demo flow runs with the network blocked and records zero network requests; pass or fail.
8. THE harness SHALL record **pack and app facts**: pack size, install size, article, passage, question and event counts, license coverage, and the validator report.
9. THE report SHALL give each rate with its sample size and a 95% Wilson confidence interval.

### R3. Harness
1. THE harness SHALL run from one command and print a full report, and SHALL write a JSON file and a Markdown file to `eval/results/` named with the date, pack hash and device.
2. THE harness SHALL run the app's real modules (search worker, Ask mode) in a real browser, not a re-implementation, so that the numbers describe the shipped app.
3. THE harness SHALL support two modes: a **desktop run** (headless Chrome, for development and continuous checks) and a **device run** (a benchmark page opened on the demo phone that runs the question set and exports timings and outputs).
4. EACH report SHALL record the commit hash, pack hash, config versions (`ask.json`), search mode, device model, browser version and run date.
5. THE harness SHALL be deterministic for accuracy measures: the same pack, config and question set SHALL give the same results.
6. THE harness SHALL fail loudly if the question set references a missing source, if the pack validator reports a failure, or if a threshold was tuned on the test split.

### R4. Threshold tuning and honest reporting
1. THE harness SHALL provide a sweep that runs the dev split across threshold values and reports the answer rate, false-answer rate and over-refusal rate for each, for each search mode.
2. THE chosen thresholds SHALL be written to `app/config/ask.json` with the run id of the sweep, and SHALL be fixed before the test split is run for the report.
3. THE report SHALL state the measured numbers as they are, with no minimum targets for accuracy; THE report SHALL list known failure types found in a sample of wrong or refused answers.
4. THE final report SHALL include a short written limits section: pack size, subjects covered, question-set size, device used and anything not measured.

### R5. Property-based tests (Kiro deliverable)
1. THE repo SHALL contain a property-based test suite with at least these properties: every displayed citation resolves to a real passage and the extract appears exactly in it; a question whose best relevance is below the threshold is always refused; every pack item has a complete license record; a quiz session never repeats a question and keeps the correct option under shuffle; link-bus calls with unknown ids never crash; and clustering conserves markers.
2. THE suite SHALL be listed in the evaluation report with the number of properties and the number of generated cases per property.
3. EACH property SHALL be traced to the spec requirement it checks, in the test file's comments.

### R6. Automation and the Kiro hook
1. THE repo SHALL contain a Kiro hook that, on a change to the pack or to `ask.json`, runs the validator and the desktop evaluation, and writes the result summary to `eval/results/latest.md`.
2. A second hook SHALL regenerate the test checklist from the specs when a spec changes.
3. THE desktop evaluation SHALL finish in under 5 minutes for pack v1 so that it can run as a hook.

### R7. Final run on the demo device
1. THE final run SHALL use the frozen build (the feature-freeze tag) and the final pack, on the demo Android phone, with the network disabled.
2. THE final run SHALL include the demo flow check (search, map, timeline, quiz, ask, refusal) with a pass or fail for each step, and a screenshot or short clip of airplane mode being on.
3. THE results file SHALL be committed whatever the numbers are, and SHALL be the source of every number quoted in the write-up, video and Devpost text.

## Out of scope
Comparing against other products, human preference studies, formal usability testing with students, measuring learning outcomes, evaluating a generative answerer.
