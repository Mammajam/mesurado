"""Tests for the timeline stage and its validator checks (spec: content-pipeline R10.3; task 6b.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from pipeline.stages.timeline import TIMELINE_YAML, TimelineError, build_timeline, containing_sentence, write_timeline
from pipeline.validate import load_pack, validate
from tests.pipeline.packfactory import build

TEXT = "Monrovia was founded in 1822 by settlers. It was renamed in 1824. The Kru live on the coast."
OTHER = "Other article text goes here, and it is long enough to be a passage."


def disk_pack(tmp_path: Path, coords: bool = True) -> Path:
    whole = [{"id": f"wp:Article{i}#000", "article": f"wp:Article{i}", "heading_path": [], "text": t, "start": 0, "end": len(t), "words": len(t.split())}
             for i, t in enumerate([TEXT, OTHER])]
    obj = build([TEXT, OTHER], passages=whole)
    root = tmp_path / "p"
    for rel, data in obj.files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data if isinstance(data, bytes) else data.read_bytes())
    if coords:
        m = json.loads((root / "manifest.json").read_text())
        m["items"][0]["coordinates"] = {"lat": 6.3, "lon": -10.8, "precision": "page"}
        (root / "manifest.json").write_text(json.dumps(m))
    return root


def source(**ev):
    event = {"id": "ev-1", "era": "a", "start": 1822, "title": "Founding", "passage": "wp:Article0#000", "quote": "founded in 1822"}
    event.update(ev)
    return {"eras": [{"id": "a", "name": "Era A", "until": 9999}], "events": [event]}


def passages_of(root: Path) -> dict:
    return {p["id"]: p for p in map(json.loads, (root / "passages.jsonl").read_text().splitlines())}


def test_summary_is_the_whole_sentence_containing_the_quote():
    assert containing_sentence("A b c. Monrovia was founded in 1822 by settlers. D e f.", "founded in 1822") == "Monrovia was founded in 1822 by settlers."


def test_quote_must_appear_exactly_once_and_sentence_must_stand_alone():
    with pytest.raises(TimelineError, match="appears 2 times"):
        containing_sentence(TEXT + " " + TEXT, "founded in 1822")
    with pytest.raises(TimelineError, match="appears 0 times"):
        containing_sentence(TEXT, "never written")
    with pytest.raises(TimelineError, match="cannot stand alone"):
        containing_sentence("Monrovia grew. It was renamed in 1824. More text follows here.", "renamed in 1824")


def test_build_sorts_events_and_reports_every_error_at_once(tmp_path):
    root = disk_pack(tmp_path)
    p = passages_of(root)
    p["wp:Article0#000"]["text"] = "Monrovia was founded in 1822 by settlers. Another sentence here."
    src = source()
    src["events"].append({"id": "ev-0", "era": "a", "start": -5, "title": "Earlier", "passage": "wp:Article0#000", "quote": "Another sentence here"})
    tl = build_timeline(src, p)
    assert [e["id"] for e in tl["events"]] == ["ev-0", "ev-1"] and tl["events"][0]["summaryType"] == "copied"
    bad = source(era="zz", passage="wp:Nope#001")
    bad["events"].append({"id": "ev-1", "era": "a", "start": 1, "title": "dup", "passage": "wp:Article0#000", "quote": "missing words"})
    with pytest.raises(TimelineError) as exc:
        build_timeline(bad, p)
    msg = str(exc.value)
    assert "unknown era" in msg and "not in the pack" in msg and "duplicate id" in msg and "appears 0 times" in msg


def test_unknown_event_keys_are_rejected():
    with pytest.raises(TimelineError, match="unknown keys"):
        build_timeline(source(colour="red"), {"wp:Article0#000": {"text": TEXT, "article": "wp:Article0"}})


def test_validator_accepts_a_built_timeline_and_flags_tampering(tmp_path):
    root = disk_pack(tmp_path)
    src = {"eras": source()["eras"], "events": [source(quote="The Kru live on the coast", place="wp:Article0")["events"][0]]}
    (tmp_path / "tl.yaml").write_text(yaml.safe_dump(src))
    tl = write_timeline(root, tmp_path / "tl.yaml")
    assert validate(load_pack(root)).error_codes() - {"META_HASH_MISMATCH"} == set()
    assert tl["events"][0]["summary"] == "The Kru live on the coast."

    tl["events"][0]["summary"] = "Something invented."
    tl["events"][0]["era"] = "nope"
    tl["events"][0]["place"] = "wp:Article1"  # exists, but has no coordinates
    (root / "timeline.json").write_text(json.dumps(tl))
    codes = validate(load_pack(root)).error_codes()
    assert {"TIMELINE_SUMMARY_NOT_COPIED", "TIMELINE_BAD_ERA", "TIMELINE_PLACE_NO_COORDINATES"} <= codes


def test_validator_flags_unsorted_events_and_warns_when_small_or_unreviewed(tmp_path):
    root = disk_pack(tmp_path)
    ev = lambda i, y: {"id": f"e{i}", "era": "a", "start": y, "title": "t", "summary": "s", "passage": "wp:Article0#000", "reviewed": False}
    (root / "timeline.json").write_text(json.dumps({"eras": [{"id": "a"}], "events": [ev(1, 1900), ev(2, 1800)]}))
    r = validate(load_pack(root))
    assert "TIMELINE_NOT_SORTED" in r.error_codes()
    assert {"TIMELINE_SMALL", "TIMELINE_UNREVIEWED"} <= {i.code for i in r.warnings}


def test_the_real_source_file_is_well_formed():
    src = yaml.safe_load(TIMELINE_YAML.read_text(encoding="utf-8"))
    ids = [e["id"] for e in src["events"]]
    assert len(ids) == len(set(ids)) >= 60
    eras = [e["id"] for e in src["eras"]]
    assert all(e["era"] in eras for e in src["events"])
    until = {e["id"]: e["until"] for e in src["eras"]}
    lower = {eid: (until[eras[i - 1]] + 1 if i else -10**9) for i, eid in enumerate(eras)}
    for e in src["events"]:  # an event sits in the era whose date range contains its start year
        assert lower[e["era"]] <= e["start"] <= until[e["era"]], e["id"]
