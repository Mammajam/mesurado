# Mesurado: project plan (local copy)

Source: Claude Doc tab "Project plan". Copied 2026-11-16. 34 tasks, 6 work packages, one builder.
Update Status here as work proceeds and commit daily.

## Gates (passed when the condition is true, not when the date arrives)
| Gate | Date | Passes when |
|---|---|---|
| M0 Rules and repo | Nov 17 | Eligibility confirmed, public repo with /.kiro committed, demo device tested |
| M1 Foundation | Nov 19 | Steering files and six specs approved; validator server started |
| M2 Offline basics | Nov 24 | Pack v1 passes validation; articles and search work in airplane mode (Tier 1 demoable) |
| M3 Grounded Ask | Nov 28 | Ask answers from retrieved passages with citations; eval harness runs; model tier works or is dropped |
| M4 Features complete | Nov 29 | Map, timeline, quizzes work offline |
| M5 Freeze | Dec 1 | Freeze tag; final eval recorded on demo device |
| M6 Recorded | Dec 2 | Demo public on YouTube; Kiro write-up complete |
| M7 Submitted | Dec 3 | Devpost complete, every field checked |

## Tasks
CUT = dropped on 2026-11-16 (2-4 h/day capacity). Ask mode ships retrieval-only (Tier 1) and the evaluation reports that. Model tiers 2 and 3 are documented as future work; keep a manual switch only if trivial.
Status: [ ] not started, [~] in progress, [x] done

### WP0-1 Setup, rules, Kiro foundation
- [x] 0.1 Read rules/FAQ; confirm Liberia + Kiro eligible. Nov 16. Done: yes/no in docs/eligibility.md (rules read; Liberia not excluded; Kiro confirmed available; see eligibility.md)
- [ ] 0.2 Request Kiro credits (ID verification). Nov 16-17. Dep 0.1. Deadline Dec 1 12:00 PM PT
- [x] 0.3 Public repo (MIT), /.kiro committed, name check. Done 2026-11-16: https://github.com/Mammajam/mesurado (no exact-name GitHub conflict; trademark and domain checks still open)
- [ ] 0.4 Test demo device: WASM, WebGPU, storage; baseline. Nov 17. Dep 0.3. Decides model tier
- [x] 1.1 Steering files (product, tech, structure, cite-or-refuse, license record). Nov 16-17. Dep 0.3 (5 files in .kiro/steering, 2026-11-16)
- [~] 1.2 Six specs (pipeline, search, Ask, map+timeline, quizzes, evaluation), each requirements/design/tasks. Nov 17-19. Dep 1.1 (content-pipeline spec drafted 2026-11-16; pipeline, search and ask-mode specs drafted; three to go)
- [ ] 1.3 Pack-validator MCP server. Nov 18-20. Dep 1.2. Fails on missing license / untraceable passage
- [ ] 1.4 Two hooks (validate+evaluate on pack change; regenerate test checklist on spec change). Nov 19-20. Dep 1.2, 1.3

### WP2 Content pipeline and pack
- [ ] 2.1 Select articles, write source manifest. Nov 18-19. Dep 1.2
- [ ] 2.2 Fetch, clean, split into passages with heading paths. Nov 19-21. Dep 2.1
- [ ] 2.3 Keyword index + embeddings. Nov 21-22. Dep 2.2
- [ ] 2.4 Package ZIM + manifest, run validator. Nov 22-23. Dep 2.3, 1.3
- [CUT] 2.5 ~~Curation agent in .kiro/agents (optional, first to cut). Nov 20-22. Dep 1.2~~

### WP3 Client app
- [ ] 3.1 PWA shell, service worker, install prompt, offline cache. Nov 19-21. Dep 0.4, 1.2
- [ ] 3.2 Article reader over ZIM. Nov 21-23. Dep 2.4, 3.1
- [ ] 3.3 Search UI (keyword + semantic). Nov 23-25. Dep 2.3, 3.1
- [ ] 3.4 Ask mode retrieval-only (Tier 1), refuses below threshold. Nov 24-25. Dep 3.3
- [CUT] 3.5 ~~Ask mode with on-device model (Tier 2), falls back to 3.4. Nov 25-28. Dep 3.4, 0.4~~
- [ ] 3.6 Offline map + timeline linked to articles. Nov 24-29. Dep 3.2
- [ ] 3.7 Quizzes from passages, source shown. Nov 26-29. Dep 3.3
- [CUT] 3.8 ~~Device tier selector + settings. Nov 27-28. Dep 3.5~~
- [ ] 3.9 Design pass: empty/error/low-power, a11y, reduced motion. Nov 29-30. Dep 3.6, 3.7

### WP4 Evaluation
- [ ] 4.1 Question set from pack passages with expected sources. Nov 22-25. Dep 2.2
- [ ] 4.2 Eval harness (accuracy, citation faithfulness, refusal, latency); one command. Nov 24-27. Dep 4.1, 3.4
- [ ] 4.3 Property-based tests (citations resolve; every item has license). Nov 25-28. Dep 1.2, 3.4
- [ ] 4.4 Final eval on demo device, results committed. Nov 30-Dec 1. Dep 3.5, 4.2

### WP5 Demo, write-up, submission
- [ ] 5.1 Feature freeze tag. Dec 1. Dep 3.9, 4.4
- [ ] 5.2 Deploy PWA to public URL. Nov 30-Dec 1. Dep 3.9
- [ ] 5.3 README, setup, license, attribution. Nov 30-Dec 1. Dep 2.4
- [ ] 5.4 Kiro usage write-up (counts, paths). Nov 29-Dec 1. Dep 1.4, 4.3
- [ ] 5.5 Record demo: airplane-mode take + 60 s backup. Dec 1-2. Dep 5.1, 5.2
- [ ] 5.6 Upload to YouTube public; check signed out. Dec 2. Dep 5.5
- [CUT] 5.7 ~~Blog + social post (bonus). Dec 2. Dep 5.4~~
- [ ] 5.8 Submit on Devpost, check fields. Dec 3. Dep 5.2, 5.3, 5.4, 5.6

## Critical path
Repo -> specs -> pack -> search -> Ask -> demo -> submission (14 tasks). Map, timeline, quizzes, tests have slack until Nov 29.

## Cut line (drop in this order)
2.5 curation agent; 5.7 posts; 3.8 tier selector (keep manual switch); 3.5 on-device model; 3.7 quizzes; 3.6 map+timeline (last).
Never cut: 0.1-0.4, 1.1-1.4, 2.1-2.4, 3.1-3.4, 4.1, 4.2, 4.4, 5.1-5.6, 5.8. 3.9 can shrink, not vanish.

## Definition of done
Committed and traced to a spec; validator and tests pass; works in airplane mode on demo device; no asset without a license record.

## Risk triggers
| Date | Trigger | Action |
|---|---|---|
| Nov 17 | Liberia ineligible / Kiro unavailable | Stop and reassess |
| Nov 23 | Pack v1 not validating | Shrink pack scope; drop 2.5 |
| Nov 25 | Tier 1 Ask not working | Pause other client tasks |
| Nov 28 | Model tier not grounded on demo device | Drop 3.5 and 3.8; demo Tier 1 on phone |
| Nov 30 | Map/timeline/quizzes unfinished | Apply cut line |
| Dec 1 | Any unfinished feature | Freeze anyway |
| Dec 2 eve | Demo take/upload not done | Use 60 s backup |

## Answers (2026-11-16)
1. Hours per day: 2-4 focused hours. The plan windows assume more, so apply the cut line early (see risk below).
2. Demo device: an Android phone running Chrome (decided 2026-11-16). Exact model and memory still to be recorded for task 0.4; a laptop is the backup.
3. Subjects beyond Liberian/African history: general science, geography, mathematics.
4. Entry: individual (one builder).
5. Subject expert: yes (name and contact to be added; schedule a review of the pack and question set).

## Risk raised by these answers
2-4 h/day over 18 days is about 36-72 hours for 34 tasks, and three extra subjects enlarge the pack work (WP2) and
the question set (4.1). The plan already warns against this (risk "Content curation takes too long": limit the
pack to one subject area plus history). Suggested default: pre-commit to dropping 2.5, 5.7, 3.8 and 3.5 now, and
start pack v1 with history + geography, adding science and mathematics only if M2 passes on time.

## Cuts applied 2026-11-16
Dropped: 2.5 curation agent, 3.5 on-device model, 3.8 tier selector, 5.7 blog and social posts.
Knock-on changes: 4.4 now depends on 4.2 only; 5.4 write-up lists no curation agent; pack v1 = history + geography first,
science and mathematics added only if gate M2 (Nov 24) passes on time. Remaining cut order if still behind: 3.7 quizzes, then 3.6 map and timeline.
