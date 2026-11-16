---
inclusion: always
---

# Technology

## Constraints (fixed)
- Everything the student uses runs on the device with no network: no runtime fetch to external hosts, no CDN
  fonts, no analytics. The only network use is the first install and pack download.
- Target: a low-end Android phone browser or laptop. Keep the app shell and per-screen work light.
- Code license: MIT. Content pack: its own licenses (CC BY-SA etc.), recorded per item.

## Candidate stack (confirm on the demo device in task 0.4 before committing)
- Installable PWA with a service worker for offline caching.
- ZIM reader in WebAssembly (Kiwix format) for articles and media.
- Offline vector-tile map for Liberia and West Africa (for example PMTiles with MapLibre).
- Keyword index plus compact embeddings for hybrid search, computed at build time, loaded in the browser.
- No generative model in the MVP. Ask mode is retrieval-only.
- Pipeline scripts in Python 3.12 (decided in the content-pipeline spec).
- Property-based tests (fast-check for JS or Hypothesis for Python) for the citation and license invariants.

## Rules
- Pin versions. Record every dependency's license in docs/third-party.md.
- Prefer small dependencies. Report the size of the app shell and pack in the README.
- Deterministic builds: the same sources and config must produce the same pack.
- Accessibility basics: keyboard use, readable contrast, reduced-motion support, text scaling.
