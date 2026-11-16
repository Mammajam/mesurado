# Content pipeline: tasks

Each task names the requirements it satisfies and the plan task it advances. Check off when done and commit with the plan id.

- [ ] 1. Project setup (plan 2.1)
  - [ ] 1.1 Create `pipeline/` package, `pyproject.toml` (Python 3.12), pinned dependencies, `pytest` and `hypothesis`. _R8_
  - [ ] 1.2 Add `selection.yaml` schema and loader with allowed-source and allowed-license checks. _R1_
  - [ ] 1.3 Draft pack v1 selection: about 40 history and 40 geography articles as a first slice, grow later. _R1_

- [ ] 2. Validator library first (plan 1.3, shared)
  - [ ] 2.1 Implement `pipeline/validate/` with the six checks in design.md and a `Report` type. _R6_
  - [ ] 2.2 Property-based tests: validate fails exactly on missing field, disallowed license, bad offsets, orphan files, "Encarta". _R6_
  - [ ] 2.3 CLI `python -m pipeline.validate <pack>` that prints a report and exits non-zero on failure. _R6.5_

- [ ] 3. Fetch and manifest (plan 2.1, 2.2)
  - [ ] 3.1 Fetch Wikipedia articles by title with a pinned revision; cache raw responses. _R2.2, R8.1_
  - [ ] 3.2 Fetch image metadata from Commons, read license from `extmetadata`, exclude when unclear. _R2.3_
  - [ ] 3.3 Write manifest entries for every fetched item. _R2.1_

- [ ] 4. Clean and passages (plan 2.2)
  - [ ] 4.1 Cleaning rules with HTML fixtures from at least 10 real pages. _R3.1_
  - [ ] 4.2 Passage splitter with heading paths, stable ids and offsets. _R3.2 to R3.4_
  - [ ] 4.3 Property-based tests for splitter bounds, offset reproduction and id stability. _R3_
  - [ ] 4.4 Report and drop empty articles. _R3.5_

- [ ] 5. Index and embeddings (plan 2.3)
  - [ ] 5.1 Build the keyword index and measure load time on the demo Android phone. _R4.1, R4.3_
  - [ ] 5.2 Compute int8 embeddings with the pinned model; write `embeddings.i8` and metadata. _R4.2_
  - [ ] 5.3 Determinism test: two builds give identical hashes. _R4.4_

- [ ] 6. Package and validate (plan 2.4)
  - [ ] 6.1 Write the ZIM with articles and compressed images. _R5.1, R5.2_
  - [ ] 6.2 Write `meta.json` with version and content hash; atomic build directory swap. _R5.3, R5.4_
  - [ ] 6.3 Generate the attribution file and per-article credit text. _R7_
  - [ ] 6.4 Generate `sample-questions.json` (at least 10 per subject, linked to passages); add its check to the validator. _R9_
  - [ ] 6.5 Run the validator as the last stage; fail the build on any error. _R6_
  - [ ] 6.6 Measure pack size and load time on the demo Android phone against the budgets. _R4.3, R5.2_

- [ ] 7. Orchestration
  - [ ] 7.1 `build.py` runs stages in order, prints progress and a summary, supports `--subjects`. _R8.2, R8.3_
  - [ ] 7.2 Integration test with a five-article fixture pack, plus a corrupted-pack test. _R6_
  - [ ] 7.3 Document the one-command build in the README. _R8.2_

## Done when
Pack v1 (history and geography) builds from one command, passes the validator with zero failures, loads on the demo Android phone within budget, and the property-based tests pass (plan gate M2).
