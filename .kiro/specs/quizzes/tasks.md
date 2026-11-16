# Quizzes: tasks

Each task names the requirements it satisfies and the plan task it advances. Commit with the plan id.
Cut order (plan): quizzes are cut after the on-device model and tier selector, before the map and timeline. If time is short, shrink the bank to 100 reviewed questions first.

- [ ] 1. Data and validator (plan 3.7, shared with 1.3)
  - [ ] 1.1 Define the question schema and `quiz-bank.json` format; add validator checks 1 to 6. _R7.1_
  - [ ] 1.2 Property-based tests for the validator (missing fields, unresolvable passage, answer not in passage, duplicate options, unreviewed). _R7.1_

- [ ] 2. Question preparation (plan 3.7, after 2.2)
  - [ ] 2.1 Rule-based candidate generator: when/how many, who/which, cloze, with same-type distractors from the same subject. _R5.4_
  - [ ] 2.2 Write candidates to `pipeline/quiz/candidates.yaml` with reproducible output. _R7.2_
  - [ ] 2.3 Review in batches (about 30 per day): accept, reject or edit; write `pipeline/quiz/reviewed.yaml`. _R5.1, R5.2_
  - [ ] 2.4 Add hand-written and assisted questions for hard types; mark `generation` correctly. _R5.2, R5.5_
  - [ ] 2.5 Build `quiz-bank.json` into the pack; report counts by subject, type and difficulty. _R5.1, R5.5_
  - [ ] 2.6 Subject expert reviews at least 50 questions; record the result in `eval/results/quiz-review.md`. _R5.6_

- [ ] 3. Session engine (plan 3.7)
  - [ ] 3.1 Seeded PRNG, weighted selection without repeats, per-session option shuffle. _R1.3, R2.2, R7.3_
  - [ ] 3.2 Scoring, timed-mode expiry, resume of an interrupted session. _R2.5, R4_
  - [ ] 3.3 Local history in IndexedDB with per-topic accuracy and "Clear my quiz data". _R4.3, R4.4_
  - [ ] 3.4 Property-based tests: no repeats, correct option preserved after shuffle, scoring, determinism, every shown question resolves. _R2, R3_

- [ ] 4. Interface (plan 3.7, 3.9)
  - [ ] 4.1 Quiz home with subject/topic chips, length, timed toggle, continue and accuracy. _R1_
  - [ ] 4.2 Question screen with four large options and progress; feedback with explanation. _R2_
  - [ ] 4.3 Source panel with passage and highlighted answer; "Open article". _R3.2_
  - [ ] 4.4 Results screen with review and retry missed; weakest-topic hint. _R4_
  - [ ] 4.5 States: no questions, loading, interrupted, data cleared; accessibility and small-screen checks. _R6_

- [ ] 5. Verification
  - [ ] 5.1 Airplane-mode run on the demo Android phone; measure start time and memory against the budgets. _R1.2, R6.4_
  - [ ] 5.2 Confirm no network requests from the quiz screens. _R6.4_
  - [ ] 5.3 Expose quiz-bank size and review pass rate to the evaluation report. _evaluation spec_

## Done when
On the demo Android phone in airplane mode, a student can run a 10-question quiz from a chosen topic, see each answer's source, review missed questions and clear their data; the bank holds
at least 200 reviewed questions (or the reduced target recorded in the plan), the validator and property-based tests pass, and the expert's review is recorded (plan 3.7, gate M4).
