---
inclusion: always
---

# Repository structure

```
.kiro/specs/         one folder per feature: requirements.md, design.md, tasks.md
.kiro/steering/      this folder
.kiro/hooks/         agent hooks
.kiro/settings/      mcp.json (pack-validator server)
docs/                brief, plan, eligibility, third-party licenses, write-up notes
pipeline/            content pack build: select, clean, index, package, validate
app/                 PWA client
eval/                question set, harness, results
tools/pack-validator/ MCP server that checks licenses, attribution, traceability
```

## Conventions
- Six specs, named: content-pipeline, search, ask-mode, map-and-timeline, quizzes, evaluation.
- Every task in docs/plan.md traces to a spec task. Commit messages name the plan task id (for example `2.2: split articles into passages`).
- Commit and push daily; update docs/plan.md statuses in the same commit.
- Never add `.kiro/` to `.gitignore`.
- Generated pack files go under `pipeline/out/`; the manifest is committed even if large binaries are not.
