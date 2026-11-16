# Mesurado: project brief (local copy)

Source of truth: the Claude Doc "Mesurado: project brief, architecture and plan"
https://claude.ai/artifact/FyFqJmEZnJn9yDeFYoLBj4 (tabs: Brief and architecture, Project plan). Copied 2026-11-16.

## What it is
Curated, offline-first learning companion for Liberian and West African students. A trusted multimedia
encyclopedia (spiritual successor to Encarta) plus an on-device AI tutor that answers only from its own
sources and shows the citation. Entry: Kiroween 2026, Resurrection track. Named after Cape Mesurado.
"Encarta" is a Microsoft trademark: never in repo, UI or demo; historical reference in the write-up only.

Users: WASSCE secondary students, teachers, school libraries with little or no connectivity.
Goal: in airplane mode a student can look up a topic, explore map and timeline, take a quiz, and ask a
question answered only from the pack, with the source passage shown.

## MVP scope (19 days)
In: articles and multimedia (from-device pack), hybrid keyword+semantic search, timeline, offline vector
map, quizzes (WASSCE-style, from passages), Liberian/African history as first focus, Ask mode.
Stretch: dictionary/thesaurus. Out: accounts, cloud sync, teacher dashboard, voice, native Android,
live updates (file copy or school-LAN only), anything not openly licensed.

## Architecture
Build pipeline (online, once) -> content pack (ZIM + indexes + manifest) -> copied to device. On device:
installable PWA + service worker, WASM ZIM reader, offline vector-tile map, WASM/WebGPU model runtime.
Optional school-LAN server shares the pack with a larger model. Candidate stack must be confirmed on the
demo device in week one.

## Content pipeline: Select -> Clean -> Index -> Package -> Validate
- Sources: Wikipedia (CC BY-SA), Wikimedia Commons, OpenStax (CC BY). Manifest records URL, license, revision.
- Passages of a few hundred words with heading path. Pack stays a few thousand articles.
- Validator fails build if any item lacks source/license/attribution or a passage is untraceable.
- Pack carries CC BY-SA + visible attribution; code is MIT or Apache-2.0. Small open-weight model with
  redistributable license, recorded in repo.

## AI design
Retrieval-first: model never answers from memory; refuses below a score threshold and offers related articles.
Tiers: 1 retrieval-only (best passages highlighted); 2 small WASM model, short grounded answers;
3 larger model on school-LAN/GPU laptop. Auto-chosen at first launch, overridable.
Guardrails: no citation, no answer; money/health/legal get passage text + professional-consult note;
quizzes store source passage; model and params fixed per release.

## Evaluation
Answer accuracy, citation faithfulness, refusal quality (false-answer rate), latency (median + worst),
offline proof (pass/fail). Question set written from pack passages, kept in repo. Report actual numbers.
Demo: one continuous airplane-mode take on cheapest device, under 3 min, plus 60 s backup.

## Kiro deliverable (/.kiro committed day one, never gitignored)
Specs (6: pipeline, search, Ask, map+timeline, quizzes, evaluation), steering (product, tech, structure,
cite-or-refuse, license-record), hooks (2), custom MCP pack-validator, curation agent, property-based tests.
Write-up must give counts and file paths and compare spec-driven vs prompt-only on one feature.

## Deadlines
Kiro credits request: Dec 1, 12:00 PM PT. Kiroween deadline: Dec 4, 2:00 PM PT. Plan submits Dec 3.

## Rules checklist (before coding)
- [ ] Read full Kiroween rules and FAQ; Liberia not excluded
- [ ] Kiro available to a Liberian account; request credits (ID verification)
- [ ] New public GitHub repo, MIT/Apache-2.0, commit /.kiro on day one (start date after Oct 30, 2026)
- [ ] No prior code in repo, or disclose exactly what is reused
- [ ] "Mesurado" free of trademark, domain, GitHub, package-name conflicts
- [ ] Plan demo video (public YouTube, no unlicensed music/marks)
- [ ] Prepare Kiro write-up
