"""Integration tests for the one-command build (spec: content-pipeline R6, R8; tasks 7.1, 7.2).

A five-article fake Wikipedia (no network) goes through every stage: fetch, clean, passages, assemble, indexes, ZIM, validator.
The Natural Earth map is replaced by a tiny SVG so the test needs no downloaded data.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from pipeline.build import BuildConfig, run_build
from pipeline.stages.index import DIMS, tokenize
from pipeline.validate import load_pack, validate

TITLES = {"history": ["Alpha Kingdom", "Beta War", "Gamma Leader"], "geography": ["Delta Town", "Epsilon River"]}
FACTS = ["founded", "expanded", "declined", "traded", "reformed"]


def sentences(title: str, n: int) -> str:
    out = []
    for i in range(n):
        out.append(f"{title} {FACTS[i % 5]} its {['markets', 'borders', 'schools', 'harbours', 'councils'][i % 5]} in {1800 + i * 7} after long debate number {i} among the people of {title}.")
    return " ".join(out)


def page_html(title: str) -> str:
    return (
        f'<div class="mw-content-ltr mw-parser-output"><p>{title} is a place studied in the test pack. {sentences(title, 14)}</p>'
        f'<div class="mw-heading mw-heading2"><h2>History</h2></div><p>{sentences(title + " history", 16)}</p>'
        f'<div class="mw-heading mw-heading2"><h2>References</h2></div><ol class="references"><li>skip</li></ol></div>'
    )


class FakeWikipedia:
    def __init__(self):
        self.calls = 0
        self.revs = {t: 1000 + i for i, t in enumerate(t for ts in TITLES.values() for t in ts)}

    def __call__(self, params):
        self.calls += 1
        if params["action"] == "query":
            pages = []
            for t in params["titles"].split("|"):
                page = {"title": t, "pageid": 7, "revisions": [{"revid": self.revs[t], "timestamp": "2026-01-01T00:00:00Z"}]}
                if t == "Delta Town":
                    page["coordinates"] = [{"lat": 6.3, "lon": -10.8, "primary": True, "globe": "earth"}]
                pages.append(page)
            return {"query": {"redirects": [], "pages": pages}}
        title = next(t for t, r in self.revs.items() if str(r) == params["oldid"])
        return {"parse": {"title": title, "text": page_html(title)}}


def fake_embedder_factory():
    calls = {"texts": 0}

    def embed(texts):
        calls["texts"] += len(texts)
        out = np.zeros((len(texts), DIMS), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in tokenize(t):
                out[i, abs(hash(tok)) % DIMS] += 1.0
            out[i] /= max(np.linalg.norm(out[i]), 1.0)
        return out

    return embed, calls


MAP_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" data-projection="equirectangular-cos" data-bbox="-18,3,15,18" '
           'data-scale="100" data-k="0.98"><g id="markers"></g></svg>')


@pytest.fixture
def env(tmp_path, monkeypatch):
    import pipeline.stages.assemble  # noqa: F401  (imported lazily inside assemble; patch the module it reads from)
    import pipeline.stages.fallback_map as fm

    monkeypatch.setattr(fm, "write_fallback_map", lambda pack, cache=None: (pack / "fallback-map.svg").write_text(MAP_SVG) or len(MAP_SVG))
    sel = tmp_path / "selection.yaml"
    sel.write_text(yaml.safe_dump({"subjects": {s: {"articles": [{"source": "wikipedia", "title": t} for t in ts]} for s, ts in TITLES.items()}}))
    tl = tmp_path / "timeline.yaml"
    tl.write_text(yaml.safe_dump({
        "eras": [{"id": "e", "name": "Era", "until": 9999}],
        "events": [
            {"id": "ev-h", "era": "e", "start": 1800, "title": "Alpha event", "passage": "wp:Alpha_Kingdom#000", "quote": "after long debate number 0 among the people of Alpha Kingdom"},
            {"id": "ev-g", "era": "e", "start": 1800, "title": "Delta event", "passage": "wp:Delta_Town#000", "quote": "after long debate number 0 among the people of Delta Town", "place": "wp:Delta_Town"},
        ]}))
    embed, calls = fake_embedder_factory()
    api = FakeWikipedia()

    def config(**over):
        base = dict(selection_path=sel, pins_path=tmp_path / "pins.json", fetch_cache=tmp_path / "cache", work_root=tmp_path / "work",
                    out_dir=tmp_path / "out", embed_cache=tmp_path / "emb.npz", timeline_source=tl, reviewed_path=tmp_path / "none.yaml",
                    http_get=api, embedder=embed, log=lambda s: None)
        base.update(over)
        return BuildConfig(**base)

    return config, api, calls, tmp_path


def test_full_build_produces_a_valid_pack_with_every_part(env):
    config, api, calls, tmp = env
    res = run_build(config())
    assert res.ok, res.error
    pack = res.pack
    assert pack.name == "dev"
    for f in ["manifest.json", "passages.jsonl", "meta.json", "attribution.json", "attribution.md", "timeline.json", "keyword.idx",
              "embeddings.i8", "sample-questions.json", "mesurado.zim", "fallback-map.svg"]:
        assert (pack / f).exists(), f
    assert validate(load_pack(pack)).ok
    meta = json.loads((pack / "meta.json").read_text())
    assert meta["articles"] == 5 and meta["subjects"] == ["geography", "history"] and "+" in meta["version"]
    assert [s[0] for s in res.stages] == ["select", "fetch", "clean", "passages", "assemble"]


def test_rebuild_is_identical_and_uses_both_caches(env):
    config, api, calls, tmp = env
    first = run_build(config())
    network_after_first, embedded_after_first = api.calls, calls["texts"]
    h1 = json.loads((first.pack / "meta.json").read_text())["content_hash"]
    second = run_build(config())
    assert second.ok and json.loads((second.pack / "meta.json").read_text())["content_hash"] == h1  # reproducible
    assert api.calls == network_after_first  # pins and fetch cache: no new network calls
    assert calls["texts"] == embedded_after_first  # embedding cache: nothing embedded again


def test_changing_one_article_embeds_only_what_changed(env):
    config, api, calls, tmp = env
    run_build(config())
    before = calls["texts"]
    api.revs["Beta War"] = 5000  # a new revision of one article, with the same fake text: still re-fetched and re-keyed
    cache_file = next((tmp / "cache").glob("1001.json"))
    rec = json.loads(cache_file.read_text())
    rec["html"] = rec["html"].replace("Beta War", "Beta Conflict", 3)
    (tmp / "cache" / "5000.json").write_text(json.dumps(rec))
    (tmp / "pins.json").write_text(json.dumps({**json.loads((tmp / "pins.json").read_text()), "Beta War": {**json.loads((tmp / "pins.json").read_text())["Beta War"], "revid": 5000}}))
    res = run_build(config())
    assert res.ok, res.error
    assert 0 < calls["texts"] - before < 40  # only the passages of the changed article, not all of them


def test_subject_build_is_partial_and_never_replaces_the_full_pack(env):
    config, api, calls, tmp = env
    full = run_build(config())
    full_hash = json.loads((full.pack / "meta.json").read_text())["content_hash"]
    part = run_build(config(subjects=["geography"]))
    assert part.ok, part.error
    assert part.pack.name == "dev-geography"
    meta = json.loads((part.pack / "meta.json").read_text())
    assert meta["partial"] is True and meta["articles"] == 2 and meta["timeline_events_dropped"] == 1
    assert json.loads((full.pack / "meta.json").read_text())["content_hash"] == full_hash  # full pack untouched
    assert validate(load_pack(part.pack)).ok


def test_failed_stage_leaves_the_previous_pack_in_place(env):
    config, api, calls, tmp = env
    good = run_build(config())
    h = json.loads((good.pack / "meta.json").read_text())["content_hash"]

    def broken(texts):
        raise RuntimeError("model crashed")

    bad = run_build(config(embedder=broken, embed_cache=tmp / "other.npz"))
    assert not bad.ok and "assemble" in bad.error and "model crashed" in bad.error
    assert json.loads((good.pack / "meta.json").read_text())["content_hash"] == h and validate(load_pack(good.pack)).ok


def test_validation_failure_is_reported_and_keeps_the_old_pack(env):
    config, api, calls, tmp = env
    good = run_build(config())
    bad_timeline = tmp / "bad-timeline.yaml"
    bad_timeline.write_text(yaml.safe_dump({"eras": [{"id": "e", "name": "E", "until": 9999}], "events": [
        {"id": "x", "era": "e", "start": 1, "title": "t", "passage": "wp:Alpha_Kingdom#000", "quote": "this text is nowhere"}]}))
    res = run_build(config(timeline_source=bad_timeline))
    assert not res.ok and "appears 0 times" in res.error
    assert validate(load_pack(good.pack)).ok


def test_offline_mode_refuses_network_and_names_the_problem(env):
    config, api, calls, tmp = env
    res = run_build(config(offline=True, http_get=None, pins_path=tmp / "nopins.json", fetch_cache=tmp / "emptycache"))
    assert not res.ok and "offline mode" in res.error
    assert not (tmp / "out" / "dev").exists()


def test_unknown_subject_fails_in_the_first_stage(env):
    config, *_ = env
    res = run_build(config(subjects=["science"]))
    assert not res.ok and res.stages[0][0] == "select" and "unknown subject" in res.error


def test_a_corrupted_pack_fails_validation_from_the_command_line(env):
    config, api, calls, tmp = env
    pack = run_build(config()).pack
    ok = subprocess.run([sys.executable, "-m", "pipeline.validate", str(pack)], capture_output=True, text=True)
    assert ok.returncode == 0 and "PASS" in ok.stdout
    victim = next((pack / "articles").glob("*.txt"))
    victim.write_text(victim.read_text(encoding="utf-8") + " tampered", encoding="utf-8")
    bad = subprocess.run([sys.executable, "-m", "pipeline.validate", str(pack)], capture_output=True, text=True)
    assert bad.returncode == 1 and "FAIL" in bad.stdout
    assert "PASSAGE_TEXT_MISMATCH" in bad.stdout or "META_HASH_MISMATCH" in bad.stdout
