"""pack-validator: an MCP server that lets an agent check the Mesurado pack while it builds.

Spec: .kiro/specs/content-pipeline (R6, R6.6), plan task 1.3. It is a thin wrapper over
pipeline.validate, so the build, the tests and the agent all run the same checks.

Run (stdio):  uv run --python 3.12 python tools/pack-validator/server.py
Read-only: it never writes files. Paths must be inside the project root
(override with the MESURADO_ROOT environment variable).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("MESURADO_ROOT", Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from pipeline.validate import DEFAULT_ALLOWED_LICENSES, Pack, load_pack, validate  # noqa: E402
from pipeline.validate.checks import check_manifest  # noqa: E402
from pipeline.validate.model import Report  # noqa: E402

mcp = FastMCP("pack-validator")


def _inside_root(path: str) -> Path:
    p = Path(path)
    p = (ROOT / p if not p.is_absolute() else p).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise ValueError(f"path must be inside the project root ({ROOT})")
    return p


@mcp.tool()
def validate_pack(path: str, max_issues: int = 50) -> str:
    """Validate an unpacked Mesurado pack directory and return a report.

    Checks licenses, attribution, passage traceability (text equals article[start:end]), files vs
    manifest, the forbidden term, the content hash, sample questions, timeline events and the quiz
    bank. Returns PASS or FAIL with counts and the first `max_issues` issues. Read-only.
    """
    pack_dir = _inside_root(path)
    report = validate(load_pack(pack_dir))
    return report.format(limit=max(1, min(max_issues, 500)))


@mcp.tool()
def check_manifest_entry(entry_json: str) -> str:
    """Check ONE proposed manifest entry (a JSON object) before it is added to a manifest.

    Verifies required fields, an allowed license, a valid source URL and that an article names its
    text file. Use this while curating sources, before any fetch. Returns PASS or the list of problems.
    """
    try:
        entry = json.loads(entry_json)
    except json.JSONDecodeError as exc:
        return f"FAIL\n  JSON_INVALID: {exc}"
    if not isinstance(entry, dict):
        return "FAIL\n  ITEM_INVALID: the entry must be a JSON object"
    report = Report()
    check_manifest(Pack(manifest={"items": [entry]}), report, DEFAULT_ALLOWED_LICENSES)
    if report.ok:
        return "PASS: entry has all required fields and an allowed license"
    return "FAIL\n" + "\n".join(f"  {i.code}: {i.message}" for i in report.errors)


@mcp.tool()
def list_allowed_licenses() -> str:
    """List the SPDX license ids the pack allows, and the required manifest fields."""
    from pipeline.validate.model import REQUIRED_ITEM_FIELDS

    return json.dumps(
        {"allowed_licenses": sorted(DEFAULT_ALLOWED_LICENSES), "required_manifest_fields": list(REQUIRED_ITEM_FIELDS)},
        indent=2,
    )


if __name__ == "__main__":
    mcp.run()
