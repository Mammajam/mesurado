# Mesurado

Offline-first, curated learning companion (Kiroween 2026, Resurrection track). Read docs/brief.md and docs/plan.md first.

## Hard rules
- Never use the word "Encarta" in code, UI, repo text or demo (trademark). Write-up only, as historical reference.
- No citation, no answer: Ask mode must refuse to show a reply with no resolvable source passage.
- Every content item needs a license record (source URL, license, revision, attribution). No unlicensed assets.
- /.kiro must be committed and never listed in .gitignore.
- Code license MIT or Apache-2.0; content pack carries CC BY-SA with visible attribution.
- Everything must work in airplane mode; no runtime network calls in the client.
- Retrieval-only (Tier 1) ships first and is always the fallback.

## Layout
- docs/ brief, plan, eligibility notes
- .kiro/{specs,steering,hooks,agents,settings} Kiro deliverables
- pipeline/ content pack build (select, clean, index, package, validate)
- app/ PWA client
- eval/ question set and evaluation harness
- tools/pack-validator/ MCP server

## Working agreement
Pick tasks from docs/plan.md, update Status, commit and push daily. Follow the cut line order if behind.
