# Quizzes: design

Implements: requirements.md (R1 to R7). Question preparation happens in the build pipeline; the app only runs sessions.

## Overview
```
BUILD (online, once)                                         PHONE (offline)
passages.jsonl -> candidate generator (rules) ->            quiz-bank.json -> session builder -> question screen
   optional assisted drafting -> human review ->              (seeded selection + shuffle)  -> feedback + source
   reviewed quiz bank -> validator -> pack/quiz-bank.json     -> results + local history
```
Nothing is generated on the phone, so quiz quality does not depend on device speed or on a model.

## Question preparation (pipeline)
1. **Rule-based candidates.** From each passage, pick sentences that state a checkable fact and build a question by pattern:
   - **When / how many:** a sentence with a year or number becomes "In which year ...?" or "How many ...?"; distractors are nearby years or numbers
     taken from other passages of the same subject, with the correct year removed.
   - **Who / which place:** a sentence with a person or place name (from article titles and heading entities) becomes "Who ...?" or "Which of
     the following ...?"; distractors are other people or places of the same type in the same subject.
   - **Cloze (fill in the blank):** blank one key term (a title, a name or a date) from a sentence; distractors from the same type.
2. **Assisted drafting (optional, build time only).** The builder may use Kiro or another assistant to draft more questions from passages, saved as
   `generation: assisted` with the passage id. Every drafted question goes through the same checks and the same human review. No question reaches the
   pack without `reviewed: true`.
3. **Hand-written questions** for hard cause-and-effect items, `generation: hand`, same checks.
4. **Review.** The builder reviews candidates in a plain file (`pipeline/quiz/candidates.yaml`, one entry each with accept/reject and edits); the subject expert
   reviews a sample of at least 50. Accepted questions are written to `pipeline/quiz/reviewed.yaml` (committed) and built into `quiz-bank.json`.

## Data format
```json
{"id":"q-0042","subject":"history","topic":"Settlement and independence","difficulty":"medium","type":"when",
 "stem":"In which year did Liberia declare its independence?",
 "options":["1822","1847","1857","1878"],"answer":1,
 "explanation":"Liberia declared independence on 26 July 1847.","explanationType":"copied",
 "passage":"wp:Liberia#012","generation":"rule","reviewed":true}
```
`options` holds the four options in stored order; the app shuffles them per session. `answer` is the index of the correct option in stored order.

## Session logic (app)
- **Selection:** from questions matching subject/topic, weight unseen first, then previously missed, then others; draw without replacement using a seeded PRNG (seed from time at start, stored in the session so it can be replayed in tests).
- **Shuffle:** Fisher-Yates with the same seeded PRNG; the correct option moves with its text.
- **Scoring:** one point per correct answer; unanswered or expired in timed mode counts as wrong.
- **State:** held in memory and saved to IndexedDB after each answer so an interrupted session can resume.
- **History:** IndexedDB (or localStorage fallback) stores per-question results and per-topic counts; "Clear my quiz data" removes it.

## Validator checks (shared library)
1. Every question has all fields, a known subject, topic and difficulty, and `reviewed: true`.
2. `passage` exists in the pack and the correct option's text appears in the passage text (normalized whitespace and case; numbers compared exactly).
3. Exactly four options, all distinct after normalization; `answer` is a valid index.
4. No distractor text appears in the stem; the stem does not contain the correct answer text (answer leak).
5. Distractor text that appears in the same passage must not be an equally valid answer: flagged for manual review if a distractor is found in the passage near the answer sentence.
6. Counts: at least 200 questions overall, spread of types and difficulties reported.

## Display
- Question screen: progress bar (numbers also in text), stem, four large option buttons (A to D), "Next" after answering.
- Feedback: right or wrong with an icon and text (not colour only), correct option marked, explanation, source line (title, heading path, license badge), passage with the answer highlighted, "Open article".
- Results: score, per-question list, "Review missed", "Retry missed", "New quiz". Weakest-topic hint.
- Quiz home: subject and topic chips, length selector, timed toggle, "Continue" if a session was interrupted, and per-topic accuracy.

## Budgets (confirm on the demo Android phone)
| Measure | Target |
|---|---|
| Quiz bank file | at most 1 MB for 500 questions |
| Start a session | under 300 ms |
| Show feedback after tap | under 100 ms |
| Memory | under 20 MB for the quiz screens |

## Testing strategy
- **Property-based (fast-check):**
  - for any bank and seed, a session never repeats a question and contains only questions from the chosen subject and topic;
  - after shuffling, the option marked correct is the same text as the stored correct option, for every question and seed;
  - scoring equals the number of answers whose chosen text equals the correct text;
  - the same seed gives the same session (determinism);
  - every question shown has a resolvable passage and its answer text is found in that passage (cite-or-refuse).
- **Property (pipeline, Hypothesis):** for any generated question set, the validator fails exactly on missing fields, unresolvable passages, answers not in passages, duplicate options and unreviewed items.
- **Unit tests:** option normalization, year and number distractor generation, cloze blanking, timed-mode expiry, resume from interrupted session.
- **Manual:** subject expert reviews at least 50 questions; the pass rate (share accepted without edits) is recorded.
- **Device:** airplane-mode run on the demo phone; record start time and memory.

## Risks
- Rule-generated questions can be awkward or ambiguous: mitigated by mandatory human review and by dropping weak patterns rather than editing many.
- Distractors that are also correct (for example two valid dates in one passage) cause unfair items: validator flag plus review.
- Reviewing 200 questions takes time on a 2 to 4 hour day: generate candidates early (plan 2.2 onward), review in batches of 30 per day, and cut the bank to 100 reviewed questions if behind (the plan can cut quizzes entirely before the map and timeline).
- Copyright: no copying of WAEC papers; stems are original and written from passages.
- Educational accuracy: questions are only as good as the pack; the subject expert's review also checks that the explanation matches the passage.
