"""Unit and integration tests for the pack validator and its CLI (spec: content-pipeline R6.5, tasks 2.3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pipeline.validate import compute_content_hash, load_pack, validate, validate_path

from .packfactory import build, make_item

TEXT = "Monrovia was named after James Monroe. " * 6


def write_pack(root: Path, pack) -> Path:
    for rel, data in pack.files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return root


def test_directory_roundtrip_passes(tmp_path):
    root = write_pack(tmp_path / "pack", build([TEXT, TEXT + " more"]))
    report = validate_path(str(root))
    assert report.ok, report.format()
    assert report.counts["articles"] == 2


def test_cli_exit_codes(tmp_path):
    root = write_pack(tmp_path / "ok", build([TEXT]))
    ok = subprocess.run([sys.executable, "-m", "pipeline.validate", str(root)], capture_output=True, text=True)
    assert ok.returncode == 0 and "PASS" in ok.stdout
    (root / "articles" / "a0.txt").write_text(TEXT + " Encarta", encoding="utf-8")
    bad = subprocess.run([sys.executable, "-m", "pipeline.validate", str(root), "--json"], capture_output=True, text=True)
    assert bad.returncode == 1
    codes = {e["code"] for e in json.loads(bad.stdout)["errors"]}
    assert "FORBIDDEN_TERM" in codes and "META_HASH_MISMATCH" in codes


def test_missing_pack_and_bad_json(tmp_path):
    assert "PACK_NOT_FOUND" in validate_path(str(tmp_path / "nope")).error_codes()
    root = write_pack(tmp_path / "p", build([TEXT]))
    (root / "manifest.json").write_text("{not json", encoding="utf-8")
    assert "JSON_INVALID" in validate_path(str(root)).error_codes()


def test_article_without_passages_and_missing_text():
    assert "ARTICLE_WITHOUT_PASSAGES" in validate(build([TEXT], passages=[])).error_codes()


def test_sample_questions_and_timeline_checks():
    items = [make_item(0), make_item(1, id="place:Monrovia", type="place", text_file=None, coordinates={"lat": 6.3, "lon": -10.8})]
    items[1].pop("text_file")
    items[1]["file"] = "places/monrovia.json"
    pack = build(
        [TEXT],
        manifest_items=items,
        extra_files={"places/monrovia.json": b"{}"},
        sample_questions=[{"subject": "history", "question": "Who was Monroe?", "passage": "wp:Missing#000"}],
        timeline={"events": [
            {"id": "e1", "title": "t", "era": "x", "summary": "s", "start": 1822, "end": 1800, "passage": "wp:Article0#000", "place": "place:Monrovia"},
            {"id": "e2", "title": "t", "era": "x", "summary": "s", "start": 1847, "passage": "wp:Article0#000", "place": "wp:Article0"},
        ]},
    )
    codes = validate(pack).error_codes()
    assert {"SAMPLE_QUESTION_BAD_PASSAGE", "TIMELINE_BAD_DATE", "TIMELINE_PLACE_NO_COORDINATES"} <= codes


def test_license_list_is_configurable():
    pack = build([TEXT], manifest_items=[make_item(0, license="MIT")])
    assert "LICENSE_NOT_ALLOWED" in validate(pack).error_codes()
    assert validate(pack, allowed_licenses={"MIT"}).ok


def test_hash_ignores_meta_and_is_order_independent():
    a = {"b.txt": b"1", "a.txt": b"2", "meta.json": b"x"}
    b = {"a.txt": b"2", "meta.json": b"y", "b.txt": b"1"}
    assert compute_content_hash(a) == compute_content_hash(b)


def test_load_pack_reads_articles(tmp_path):
    root = write_pack(tmp_path / "pack", build([TEXT]))
    pack = load_pack(root)
    assert pack.articles["wp:Article0"] == TEXT
