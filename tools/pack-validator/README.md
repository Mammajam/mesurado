# pack-validator

MCP server wrapping `pipeline.validate`, so an agent can check licenses, attribution and passage
traceability while it builds the pack. Read-only; paths must be inside the project root.

Tools: `validate_pack(path, max_issues)`, `check_manifest_entry(entry_json)`, `list_allowed_licenses()`.

Run: `uv run --python 3.12 python tools/pack-validator/server.py` (stdio). Registered for Kiro in `.kiro/settings/mcp.json`.
Same checks from the command line: `uv run python -m pipeline.validate <pack-dir> [--json]`.
Tests: `uv run pytest`.
