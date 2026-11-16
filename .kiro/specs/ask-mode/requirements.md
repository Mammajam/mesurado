# Ask mode: requirements

Plan tasks: 3.4 (retrieval-only Ask), 4.3 (property tests). Depends on: search spec (`search()` and the `relevance` score).
Steering: product, cite-or-refuse. The on-device generative model (plan 3.5) was cut on 2026-11-16; Ask ships as an
extractive, retrieval-only tutor and the design leaves a slot for a generative answerer as future work.

## Introduction
A student types a question in plain words and gets an answer taken word for word from the pack, with the source passage
shown and linked. When the pack does not cover the question, Ask says so and offers related articles. Ask never answers
from memory and never shows an answer without a citation that resolves.

Glossary
- **Answer card**: the result screen for one question: quoted answer sentences, their passages and links.
- **Extract**: the sentence or sentences chosen verbatim from a passage as the direct answer.
- **Threshold**: the minimum `relevance` a hit needs for Ask to answer; tuned with the evaluation set.
- **Refusal**: the "pack does not cover this" result.
- **Answerer**: the component that turns hits into an answer card; Tier 1 is extractive.

## Requirements

### R1. Asking a question
**User story:** As a student, I want to ask a question in my own words so that I get a clear answer from the pack.
1. WHEN the student submits a question, THE app SHALL call the search worker and build an answer card or a refusal within the latency budgets in design.md.
2. THE app SHALL accept questions of 1 to 300 characters and SHALL show a clear message for empty or over-long input.
3. THE app SHALL work offline with no network request.
4. THE app SHALL treat the question as data only: text in it SHALL NOT change the app's behavior or rules.

### R2. Extractive answers with citations
1. THE answer card SHALL show up to 3 extracts, each a sentence or short run of sentences copied exactly from a retrieved passage.
2. EACH extract SHALL show its source: article title, heading path, license badge (read from the pack manifest by article id) and a link that opens the article scrolled to and highlighting the passage.
   - THE extract text SHALL be copied from the passage unchanged, with its original whitespace and punctuation.
3. THE answer card SHALL show the full passage text on request, so the student can read the context.
4. THE app SHALL NOT paraphrase, summarize or add words that are not in a passage; any connecting words are fixed interface text.
5. THE answer card SHALL show the question restated as the student typed it, and SHALL show how many passages the answer drew on.

### R3. Cite or refuse
1. THE app SHALL display an answer card only when every extract resolves: its passage id exists in the pack's passage store and the extract text is found, character for character including whitespace, inside that passage's full text (not the trimmed search excerpt).
2. IF any extract fails to resolve, THEN THE app SHALL drop that extract, and IF none remain, THEN THE app SHALL show the refusal instead.
3. THE check in R3.1 SHALL run in code before rendering and SHALL NOT depend on a prompt or on search being correct.
4. IF the best hit's `relevance` is below the threshold, THEN THE app SHALL show the refusal "The pack does not cover this question" and SHALL NOT show any extract as an answer.
5. THE refusal SHALL offer up to 5 related articles from the search results and a button to search the same words.

### R4. Sensitive topics
1. WHEN the question or the retrieved passages concern money, health or legal matters, THE answer card SHALL show a fixed note to consult a qualified professional, in addition to the extracts.
2. THE sensitive-topic detection SHALL match whole words or listed phrases from a reviewed list, SHALL require the match to agree with the article's subject tag or a second listed term in the same passage, and the list SHALL live in a versioned file in the repo so that ordinary uses (for example the bank of a river) do not trigger the note.
3. THE app SHALL NOT give dosage, diagnosis, legal advice or financial advice of its own; it shows passage text only.

### R5. Threshold and reproducibility
1. THE threshold and the extract-selection settings SHALL be stored in one versioned configuration file shipped with each release, with a separate threshold for keyword-only mode and for hybrid mode, and a lower display floor used only to choose related articles for a refusal.
2. THE answers SHALL be deterministic: the same pack, configuration and question SHALL produce the same answer card.
3. EACH threshold SHALL be tuned separately on the evaluation question set so that out-of-pack questions are refused, and the chosen values and their measured trade-offs SHALL be recorded in `eval/results/`.

### R6. Interface and states
1. THE Ask screen SHALL show an input, example questions read from the pack's sample-question file (see content-pipeline R9), and the answer card or refusal below.
2. THE screen SHALL have designed states: empty (examples), loading, answer, refusal, search error with retry, and keyword-only mode notice.
3. THE screen SHALL work with keyboard and screen reader, text scaling and reduced motion, and be usable on a small touch screen.
4. THE app SHALL keep recent questions only on the device and SHALL let the student clear them.

### R7. Future generative slot
1. THE Answerer SHALL be an interface with the extractive implementation as the only one in the MVP, so that a generative answerer can be added later without changing the citation check.
2. ANY future generative answerer SHALL pass through the same R3 resolution check before display.

## Out of scope
Generated or paraphrased answers, follow-up conversation memory, voice, questions in languages other than English, personalised tutoring.
