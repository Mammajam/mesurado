# Mesurado

An offline-first, curated learning companion for students in Liberia and West Africa (WASSCE preparation). A small,
openly licensed content pack is built once, copied to a phone, and works with no network: search, a map, a timeline,
quizzes, and an "Ask" mode that only answers with a cited passage from the pack (no source, no answer).

Entry for Kiroween 2026, Resurrection track. The plan and the architecture are in [docs/brief.md](docs/brief.md) and
[docs/plan.md](docs/plan.md); the Kiro specs, steering files and hooks are in [.kiro/](.kiro/).

## Status

| Part | State |
|---|---|
| Content pipeline (select, fetch, clean, passages, indexes, embeddings, ZIM, attribution, timeline, sample questions, fallback map, validator) | working, 108 tests |
| Quiz bank | candidates generated; the bank stays empty until questions are reviewed by a person |
| Vector map (`map.pmtiles`), images, pack size and speed on the demo phone | not started |
| App (PWA: reader, search, map, timeline, quizzes, Ask) | not started |

## Build the content pack

Needs [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 and the dependencies).

```bash
uv run --python 3.12 python -m pipeline.build
```

The command prints each stage and a summary, and writes the pack to `pipeline/out/dev/`. It stops at the first failing
stage, and the previous pack is replaced only if the validator passes.

| Option | Effect |
|---|---|
| `--offline` | never use the network; works from the pins and the caches (a full rebuild takes under 10 seconds) |
| `--subjects history` | build one subject into `pipeline/out/dev-history/`; never replaces the full pack |

Caches (`pipeline/cache/`, ignored by git): fetched articles by revision, Natural Earth map data, and embedding vectors.
`pipeline/pins.json` pins every article to a revision, so a rebuild fetches the same text.

Check any pack directory on its own (exit code 1 on any error):

```bash
uv run --python 3.12 python -m pipeline.validate pipeline/out/dev
```

Run the tests (the real embedding model test is skipped unless you add `-m slow`):

```bash
uv run --python 3.12 pytest
```

## What is in a pack

`manifest.json` (every item with source URL, revision, license and attribution), `passages.jsonl`, `articles/*.txt`,
`mesurado.zim`, `keyword.idx`, `embeddings.i8`, `timeline.json`, `sample-questions.json`, `fallback-map.svg`,
`attribution.json` and `attribution.md`, and `meta.json` (version and content hash). Rules the validator enforces: every
item has an allowed license and attribution, every passage is an exact slice of its article, every file is listed,
indexes describe exactly the passages, timeline events and quiz answers trace to a passage.

## Licenses

- Code: MIT, see [LICENSE](LICENSE).
- Content: each item carries its own license in the manifest. The pack is distributed under CC BY-SA 4.0 with visible
  attribution, see [CONTENT-LICENSE.md](CONTENT-LICENSE.md). Articles are adapted from Wikipedia (CC BY-SA 4.0);
  map data is from Natural Earth (public domain).
- Embedding model: all-MiniLM-L6-v2 (Apache-2.0).
