---
inclusion: always
---

# Cite or refuse

Ask mode must never display an answer without a citation that resolves to a real passage in the pack.

## Rules
1. Ask answers come only from passages returned by search. Never from memory, never from a model's own knowledge.
2. Every displayed answer carries one or more citations. Each citation resolves to a passage id that exists in the
   pack and links to its source article.
3. If the best passage scores below the threshold, show "The pack does not cover this question" and offer related
   articles. Do not guess.
4. Money, health and legal topics: show the passage text plus the fixed note to consult a professional.
5. Quiz questions store the passage they came from and show it with the answer.
6. The interface refuses to render a reply whose citations fail to resolve. This check lives in code, not in a prompt.

## Tests required
- Property: for any question, every displayed citation resolves to a real passage.
- Property: a question with no passage above the threshold always produces a refusal.
- Evaluation reports refusal quality (false-answer rate) from out-of-pack questions.

## Never
- Invent a source, quote or passage id.
- Show a partial answer when citation resolution fails.
