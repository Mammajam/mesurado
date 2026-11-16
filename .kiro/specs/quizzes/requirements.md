# Quizzes: requirements

Plan task: 3.7 (quizzes generated from passages); 3.9 for states and accessibility. Depends on: content-pipeline (quiz bank in the pack),
the article reader (plan 3.2) and, optionally, search (plan 3.3). Steering: product, cite-or-refuse, license-record.
The on-device generative model was cut, so quiz questions are prepared at build time and stored in the pack, not generated on the phone.

## Introduction
The quiz feature helps students practise for WASSCE-style objective questions on the pack's topics. Each question is
tied to the passage it came from, so every answer can be checked and the student can read the source straight away.
Quizzes run fully offline, keep results only on the device, and never show a question whose source cannot be resolved.

Glossary
- **Quiz bank**: the set of questions stored in the pack (`quiz-bank.json`).
- **Question**: a stem, four options, the index of the correct option, an explanation, a source passage id, a subject, a topic and a difficulty.
- **Session**: one run of a quiz (default 10 questions) with a score at the end.
- **WASSCE-style**: objective multiple choice with four options (A to D) and one correct answer, written in the plain exam register.

## Requirements

### R1. Starting a quiz
**User story:** As a student, I want to pick a topic and start a short quiz so that I can practise in a few minutes.
1. THE quiz home SHALL let the student choose a subject and topic, or "mixed", and a length of 5, 10 or 20 questions.
2. THE app SHALL start a session within 300 ms on the demo Android phone and with no network request.
3. THE app SHALL pick questions at random without repeats inside a session, favouring questions the student has not seen or got wrong before.
4. IF fewer questions exist for a choice than the length asked, THEN THE app SHALL run a shorter session and say so.

### R2. Taking a quiz
1. EACH question screen SHALL show the question number, the stem, and four options labelled A to D with large touch targets.
2. THE order of options SHALL be shuffled per session from a seed, and the shuffle SHALL keep exactly one correct option.
3. WHEN the student selects an option, THE app SHALL show at once whether it was right, mark the correct option, and show the explanation and the source.
4. THE app SHALL let the student move to the next question only after answering, and SHALL allow quitting at any time without losing earlier answers.
5. WHERE the student chooses timed mode, THE app SHALL show a countdown per question (default 60 seconds) and count an expired question as wrong; timed mode SHALL be off by default.

### R3. Source and citation
1. EACH question SHALL carry a source passage id that exists in the pack, and the correct answer text SHALL appear in that passage.
2. AFTER answering, THE app SHALL show the source: article title, heading path, license badge and the passage text with the answer highlighted, plus "Open article".
3. THE app SHALL NOT display a question whose passage id does not resolve or whose correct answer is not found in the passage.
4. THE explanation SHALL be written from the passage, and any text not copied from the passage SHALL be marked as the project's own wording.

### R4. Results and review
1. AT THE END of a session, THE app SHALL show the score, the percentage and a list of questions with right or wrong marks.
2. THE student SHALL be able to review any missed question with its source, and retry only the missed questions.
3. THE app SHALL store session history, per-topic accuracy and the set of missed questions on the device only, with a visible "Clear my quiz data" control.
4. THE app SHALL show per-topic accuracy and suggest the weakest topic, without accounts or sync.

### R5. Quiz bank quality
1. THE quiz bank SHALL hold at least 200 questions for pack v1 (history and geography), at least 100 of them in Liberian and African history, and SHALL grow with science and mathematics only if the plan allows.
2. EACH question SHALL be marked `generation: rule | assisted | hand` and `reviewed: true | false`; ONLY reviewed questions SHALL ship.
3. THE questions SHALL be original: they SHALL NOT copy past WAEC or other exam papers, and SHALL be written in WASSCE style rather than taken from it.
4. EACH question SHALL have exactly four distinct options; THE distractors SHALL be plausible items of the same type (for example other dates, people or places from the same subject) and SHALL NOT be correct according to the source passage.
5. THE bank SHALL include a spread of difficulties (easy, medium, hard) and of question types (who, what, when, where, which, cause and effect).
6. THE subject expert SHALL review a sample of at least 50 questions before release, and the review result SHALL be recorded in `eval/results/`.

### R6. Interface and states
1. THE quiz screens SHALL be designed for a small touch screen, with readable text, clear right and wrong states that do not rely on colour alone, and no flashing animation.
2. THE app SHALL have designed states: no questions for the choice, loading, question, feedback, results, quiz interrupted (resume or discard) and data cleared.
3. THE screens SHALL work with keyboard and screen readers, text scaling and reduced motion.
4. THE app SHALL send no network requests from the quiz screens.

### R7. Validation and reproducibility
1. THE validator SHALL fail the build if any question has a missing field, an unresolvable passage, a correct answer not in the passage, fewer or more than four distinct options, or an unreviewed flag.
2. THE quiz bank SHALL be reproducible: the same selection, passages and generation settings SHALL produce the same unreviewed candidates, and the reviewed file SHALL be committed.
3. THE session logic (selection, shuffle, scoring) SHALL be deterministic for a given seed.

## Out of scope
Generating questions on the phone, free-text answers, leaderboards or sharing, accounts, teacher dashboards, adaptive difficulty beyond "seen and missed first", questions in other languages.
