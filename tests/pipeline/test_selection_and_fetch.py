"""Tests for the selection loader and the fetch stage (spec: content-pipeline R1, R2, R8.1; tasks 1.2, 3.1, 3.3).

No network: the MediaWiki API is replaced by a fake that records its calls.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.selection import DEFAULT_SELECTION, SelectionError, load_selection, parse_selection
from pipeline.stages import fetch as F
from pipeline.validate import Pack, Report
from pipeline.validate.checks import check_manifest
from pipeline.validate.model import DEFAULT_ALLOWED_LICENSES


def sel(*titles, source="wikipedia", subject="history"):
    return parse_selection({"subjects": {subject: {"articles": [{"source": source, "title": t} for t in titles]}}})


# ---- selection -------------------------------------------------------------------------------


def test_shipped_selection_is_valid_and_grouped():
    s = load_selection(DEFAULT_SELECTION)
    assert set(s.subjects) == {"history", "geography"}
    assert len(s.articles()) >= 80
    assert len(s.articles(["history"])) < len(s.articles())


def test_disallowed_source_names_the_source():
    with pytest.raises(SelectionError, match="britannica"):
        sel("Liberia", source="britannica")


def test_unquoted_comma_title_is_rejected():
    import yaml

    data = yaml.safe_load("subjects:\n  h:\n    articles:\n      - {source: wikipedia, title: Buchanan, Liberia}\n")
    with pytest.raises(SelectionError, match="unexpected key"):
        parse_selection(data)


def test_disallowed_license_and_unknown_subject():
    with pytest.raises(SelectionError, match="GPL"):
        parse_selection({"allowed_licenses": ["GPL-3.0"], "subjects": {"a": {"articles": [{"source": "wikipedia", "title": "X"}]}}})
    with pytest.raises(SelectionError, match="unknown subject"):
        sel("Liberia").articles(["science"])


@settings(max_examples=50, deadline=None)
@given(st.text(alphabet="abcdefg hij", min_size=1, max_size=15).map(str.strip).filter(bool))
def test_duplicates_detected_across_case_and_underscores(title):
    a, b = title, title.upper().replace(" ", "_")
    with pytest.raises(SelectionError, match="duplicate"):
        sel(a, b)


# ---- fetch -----------------------------------------------------------------------------------


class FakeApi:
    """Tiny stand-in for the MediaWiki API."""

    def __init__(self):
        self.calls: list[dict[str, str]] = []
        self.pages = {
            "Liberia": {"title": "Liberia", "pageid": 1, "revisions": [{"revid": 111, "timestamp": "2026-01-01T00:00:00Z"}],
                         "coordinates": [{"lat": 6.5, "lon": -9.5, "primary": True, "globe": "earth"}]},
            "Monrovia": {"title": "Monrovia", "pageid": 2, "revisions": [{"revid": 222, "timestamp": "2026-02-01T00:00:00Z"}]},
            "Bad (disambiguation)": {"title": "Bad (disambiguation)", "pageid": 3, "revisions": [{"revid": 333, "timestamp": "x"}],
                                      "pageprops": {"disambiguation": ""}},
        }
        self.redirects = {"Cape Mesurado": "Monrovia", "Monrovia, Liberia": "Monrovia"}

    def __call__(self, params):
        self.calls.append(params)
        if params["action"] == "query":
            titles = params["titles"].split("|")
            redirects = [{"from": t, "to": self.redirects[t]} for t in titles if t in self.redirects]
            names = {self.redirects.get(t, t) for t in titles}
            pages = [self.pages[n] if n in self.pages else {"title": n, "missing": True} for n in sorted(names)]
            return {"query": {"redirects": redirects, "pages": pages}}
        if params["action"] == "parse":
            return {"parse": {"title": "T", "text": f"<p>revision {params['oldid']}</p>"}}
        raise AssertionError(params)

    def count(self, action):
        return sum(1 for c in self.calls if c["action"] == action)


@pytest.fixture
def dirs(tmp_path):
    return dict(pins_path=tmp_path / "pins.json", cache_dir=tmp_path / "cache", work_dir=tmp_path / "work")


def test_fetch_resolves_redirects_and_writes_manifest_entries(dirs):
    api = FakeApi()
    res = F.fetch(sel("Liberia", "Cape Mesurado"), http_get=api, **dirs)
    assert res.ok, res.problems
    ids = [i["id"] for i in res.items]
    assert ids == ["wp:Liberia", "wp:Monrovia"]  # redirect resolved to the final title
    liberia = res.items[0]
    assert liberia["revision"] == "111" and liberia["coordinates"]["lat"] == 6.5
    assert "oldid=111" in liberia["source_url"]
    pins = json.loads(dirs["pins_path"].read_text())
    assert pins["Cape Mesurado"]["title"] == "Monrovia"
    work = list((dirs["work_dir"] / "history").glob("*.json"))
    assert len(work) == 2 and "revision 111" in work[0].read_text() + work[1].read_text()


def test_manifest_entries_pass_the_validator_manifest_check(dirs):
    res = F.fetch(sel("Liberia", "Monrovia"), http_get=FakeApi(), **dirs)
    for item in res.items:
        item = {**item, "text_file": "articles/x.txt"}  # assigned later, at packaging
        report = Report()
        check_manifest(Pack(manifest={"items": [item]}), report, DEFAULT_ALLOWED_LICENSES)
        assert report.ok, report.format()


def test_second_run_uses_pins_and_cache_without_network(dirs):
    api = FakeApi()
    F.fetch(sel("Liberia", "Monrovia"), http_get=api, **dirs)
    assert api.count("query") == 1 and api.count("parse") == 2
    again = FakeApi()
    res = F.fetch(sel("Liberia", "Monrovia"), http_get=again, **dirs)
    assert res.ok and again.calls == []  # reproducible: same revisions, no requests
    assert [i["retrieved_at"] for i in res.items] == [i["retrieved_at"] for i in res.items]


def test_problems_are_reported_without_stopping_others(dirs):
    res = F.fetch(sel("Liberia", "No Such Page", "Bad (disambiguation)"), http_get=FakeApi(), **dirs)
    assert [i["id"] for i in res.items] == ["wp:Liberia"]
    text = " ".join(res.problems)
    assert "No Such Page: page not found" in text and "disambiguation" in text
    assert not res.ok


def test_two_titles_resolving_to_one_article_are_flagged(dirs):
    res = F.fetch(sel("Monrovia", "Monrovia, Liberia"), http_get=FakeApi(), **dirs)
    assert [i["id"] for i in res.items] == ["wp:Monrovia"]
    assert any("already selected" in p for p in res.problems)


def test_limit_and_subject_filters(dirs):
    s = parse_selection({"subjects": {
        "history": {"articles": [{"source": "wikipedia", "title": "Liberia"}]},
        "geography": {"articles": [{"source": "wikipedia", "title": "Monrovia"}]},
    }})
    assert [i["id"] for i in F.fetch(s, subjects=["geography"], http_get=FakeApi(), **dirs).items] == ["wp:Monrovia"]


@settings(max_examples=100, deadline=None)
@given(st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=30, unique=True))
def test_slugs_are_filesystem_safe_and_unique(titles):
    ids = [F.article_id(t) for t in titles]
    slugs = [F.slug(i) for i in ids]
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+", s) for s in slugs)
    assert len(set(slugs)) == len(set(ids))
