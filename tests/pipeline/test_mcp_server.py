"""Smoke test: the pack-validator MCP server starts over stdio and its tools work (plan task 1.3 done-when)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .packfactory import build

ROOT = Path(__file__).resolve().parents[2]
TEXT = "Monrovia was named after James Monroe. " * 6


def _write(root: Path, pack) -> None:
    for rel, data in pack.files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


async def _run(good: Path, bad: Path) -> dict[str, str]:
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "tools/pack-validator/server.py")], env={"MESURADO_ROOT": str(good.parent)})
    out: dict[str, str] = {}
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            out["tools"] = ",".join(sorted(t.name for t in (await s.list_tools()).tools))
            out["good"] = (await s.call_tool("validate_pack", {"path": str(good)})).content[0].text
            out["bad"] = (await s.call_tool("validate_pack", {"path": str(bad)})).content[0].text
            out["entry_bad"] = (await s.call_tool("check_manifest_entry", {"entry_json": '{"id":"x","type":"article","license":"GPL-3.0"}'})).content[0].text
            out["outside"] = (await s.call_tool("validate_pack", {"path": "/etc"})).content[0].text
    return out


def test_server_end_to_end(tmp_path):
    good, bad = tmp_path / "good", tmp_path / "bad"
    _write(good, build([TEXT]))
    _write(bad, build([TEXT], manifest_items=None, extra_files={"stray.bin": b"x"}))
    out = asyncio.run(_run(good, bad))
    assert out["tools"] == "check_manifest_entry,list_allowed_licenses,validate_pack"
    assert "PASS" in out["good"]
    assert "FAIL" in out["bad"] and "FILE_NOT_IN_MANIFEST" in out["bad"]
    assert "LICENSE_NOT_ALLOWED" in out["entry_bad"] and "ITEM_FIELD_MISSING" in out["entry_bad"]
    assert "inside the project root" in out["outside"]
