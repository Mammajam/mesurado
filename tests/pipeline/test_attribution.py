"""Tests for the attribution stage and its validator check (spec: content-pipeline R7; task 6.3)."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.stages.attribution import LICENSE_URLS, build_attribution, credit_text, render_markdown, write_attribution
from pipeline.validate import load_pack, validate
from pipeline.validate.model import DEFAULT_ALLOWED_LICENSES
from tests.pipeline.packfactory import build, make_item

TEXTS = ["Monrovia is the capital of Liberia. " * 4, "The Kru people live on the coast. " * 5]


def disk_pack(tmp_path: Path) -> Path:
    obj = build(TEXTS)
    root = tmp_path / "p"
    for rel, data in obj.files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data if isinstance(data, bytes) else data.read_bytes())
    return root


def test_credit_text_names_title_author_revision_license_and_changes():
    c = credit_text(make_item(1))
    assert "Article 1" in c and "Wikipedia contributors" in c and "revision 1001" in c
    assert "CC BY-SA 4.0" in c and "cleaned, split into passages" in c


def test_every_allowed_license_has_a_url():
    assert DEFAULT_ALLOWED_LICENSES <= set(LICENSE_URLS)


def test_attribution_lists_every_item_in_json_and_markdown():
    items = [make_item(i, history_url=f"https://example.org/h{i}") for i in range(3)]
    att = build_attribution(items)
    assert [e["id"] for e in att["items"]] == sorted(i["id"] for i in items)
    assert att["pack_license"] == "CC-BY-SA-4.0"
    md = render_markdown(att)
    assert all(i["title"] in md and i["history_url"] in md for i in items)


def test_written_files_validate_and_tampering_is_caught(tmp_path):
    root = disk_pack(tmp_path)
    write_attribution(root)
    # Adding files after the factory wrote meta.json changes the content hash; every other check must pass.
    assert validate(load_pack(root)).error_codes() == {"META_HASH_MISMATCH"}

    att = json.loads((root / "attribution.json").read_text())
    att["items"][0]["license"] = "CC0-1.0"
    att["items"][1]["credit"] = "Somebody"
    att["items"].append({**att["items"][0], "id": "wp:Ghost"})
    (root / "attribution.json").write_text(json.dumps(att))
    codes = validate(load_pack(root)).error_codes()
    assert {"ATTRIBUTION_MISMATCH", "ATTRIBUTION_CREDIT_WEAK", "ATTRIBUTION_ITEM_EXTRA"} <= codes


def test_missing_item_and_missing_file(tmp_path):
    root = disk_pack(tmp_path)
    assert "ATTRIBUTION_MISSING" in {i.code for i in validate(load_pack(root)).warnings}
    write_attribution(root)
    att = json.loads((root / "attribution.json").read_text())
    att["items"].pop()
    (root / "attribution.json").write_text(json.dumps(att))
    assert "ATTRIBUTION_ITEM_MISSING" in validate(load_pack(root)).error_codes()
