"""Tests for the ZIM packaging stage and its validator check (spec: content-pipeline R5.1; task 6.1)."""

from __future__ import annotations

import json
from pathlib import Path

from libzim.reader import Archive

from pipeline.stages.package import ZIM_NAME, package_zim
from pipeline.validate import compute_content_hash, load_pack, validate
from tests.pipeline.packfactory import build

TEXTS = ["Monrovia is the capital of Liberia. Café ünïcode ok. " * 4, "The Kru people live on the coast. " * 5]


def disk_pack(tmp_path: Path) -> Path:
    obj = build(TEXTS)
    root = tmp_path / "p"
    for rel, data in obj.files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data if isinstance(data, bytes) else data.read_bytes())
    return root


def test_zim_contains_every_article_byte_for_byte(tmp_path):
    root = disk_pack(tmp_path)
    out = package_zim(root)
    assert out.name == ZIM_NAME
    zim = Archive(out)
    for i, text in enumerate(TEXTS):
        entry = zim.get_entry_by_path(f"articles/a{i}.txt")
        assert bytes(entry.get_item().content).decode("utf-8") == text
    assert zim.get_metadata("License").decode() == "CC-BY-SA-4.0"


def test_validator_accepts_a_good_zim_and_hash_ignores_it(tmp_path):
    root = disk_pack(tmp_path)
    before = compute_content_hash(load_pack(root).files)
    package_zim(root)
    pack = load_pack(root)
    assert compute_content_hash(pack.files) == before  # random UUID must not change the content hash
    assert validate(pack).ok


def test_validator_rejects_missing_changed_and_extra_entries(tmp_path):
    root = disk_pack(tmp_path)
    package_zim(root)
    (root / "articles/a0.txt").write_text(TEXTS[0] + "edited", encoding="utf-8")  # pack file changed after packaging
    assert "ZIM_ENTRY_MISMATCH" in validate(load_pack(root)).error_codes()

    root2 = disk_pack(tmp_path / "two")
    manifest = json.loads((root2 / "manifest.json").read_text())
    kept = manifest["items"][:1]
    (root2 / "manifest.json").write_text(json.dumps({"items": manifest["items"]}))
    package_zim(root2)
    # Rebuild the ZIM from a manifest with one article, then restore the full manifest: one entry is missing.
    (root2 / "manifest.json").write_text(json.dumps({"items": kept}))
    package_zim(root2)
    (root2 / "manifest.json").write_text(json.dumps({"items": manifest["items"]}))
    assert "ZIM_ENTRY_MISSING" in validate(load_pack(root2)).error_codes()


def test_validator_rejects_a_corrupt_zim(tmp_path):
    root = disk_pack(tmp_path)
    (root / ZIM_NAME).write_bytes(b"not a zim file at all")
    assert "ZIM_UNREADABLE" in validate(load_pack(root)).error_codes()
