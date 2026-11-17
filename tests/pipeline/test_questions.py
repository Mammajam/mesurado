"""Tests for the rule-based sample questions (spec: content-pipeline R9; task 6.4)."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.stages.index import build_keyword_index
from pipeline.stages.questions import PER_SUBJECT, build_sample_questions, lead_question, write_sample_questions
from pipeline.validate import load_pack, validate
from tests.pipeline.packfactory import build


def test_lead_questions_distinguish_people_things_and_plurals():
    assert lead_question("William Tolbert", "William Richard Tolbert Jr. (May 13, 1913 – April 12, 1980) was the 20th president of Liberia.") == "Who was William Tolbert?"
    assert lead_question("Leymah Gbowee", "Leymah Roberta Gbowee (born 1972) is a Liberian peace activist.") == "Who is Leymah Gbowee?"
    assert lead_question("Lake Piso", "Lake Piso is a coastal lagoon.") == "What is Lake Piso?"
    assert lead_question("Sierra Leone Civil War", "The Sierra Leone Civil War (1991–2002) was a civil war.") == "What was Sierra Leone Civil War?"
    assert lead_question("Americo-Liberian people", "Americo-Liberian people are an ethnic group.") == "What are Americo-Liberian people?"


def test_no_question_when_the_first_sentence_is_not_a_definition():
    assert lead_question("Politics of Liberia", "Politics of Liberia takes place in the framework of a presidential republic.") is None
    # "General Act" later in the sentence must not make a conference a person
    assert lead_question("Berlin Conference", "The Berlin Conference was a meeting of colonial powers that signed the General Act.") == "What was Berlin Conference?"


def passage(aid: str, n: int, text: str, heading: list[str] | None = None) -> dict:
    return {"id": f"{aid}#{n:03d}", "article": aid, "heading_path": heading or [], "text": text, "start": 0, "end": len(text), "words": len(text.split())}


def sample_data(n_articles: int = 30):
    items, passages = [], []
    for i in range(n_articles):
        aid = f"wp:Place{i}"
        items.append({"id": aid, "type": "article", "title": f"Place{i}", "subject": "geography" if i % 2 else "history"})
        passages.append(passage(aid, 0, f"Place{i} is a town in Liberia with number{i} markers."))
        passages.append(passage(aid, 1, f"The history of Place{i} began long ago with number{i} settlers.", ["History"]))
    return passages, items


def test_selection_is_capped_spread_and_deterministic():
    passages, items = sample_data()
    a = build_sample_questions(passages, items)
    assert a == build_sample_questions(passages, items)
    for subject in ("geography", "history"):
        qs = [q for q in a if q["subject"] == subject]
        assert len(qs) == PER_SUBJECT
        assert len({q["article"] for q in qs}) >= 15  # spread over articles
        assert any(q["method"].endswith("heading") for q in qs)
    assert all(q["method"].startswith("rule-based:") for q in a)


def test_questions_the_search_cannot_answer_are_dropped():
    passages, items = sample_data(6)
    kw = build_keyword_index(passages, {i["id"]: i["title"] for i in items})
    kept = build_sample_questions(passages, items, kw)
    assert kept  # these questions do retrieve their passage
    kw["postings"] = {}  # an index that finds nothing
    assert build_sample_questions(passages, items, kw) == []


@settings(max_examples=30, deadline=None)
@given(st.integers(1, 40), st.integers(1, 30))
def test_every_question_links_to_an_existing_passage(n_articles, per_subject):
    passages, items = sample_data(n_articles)
    ids = {p["id"] for p in passages}
    qs = build_sample_questions(passages, items, per_subject=per_subject)
    assert all(q["passage"] in ids and q["question"].endswith("?") for q in qs)
    assert len({(q["subject"], q["question"]) for q in qs}) == len(qs)  # no duplicates
    for subject in {q["subject"] for q in qs}:
        assert sum(q["subject"] == subject for q in qs) <= per_subject


def test_written_file_passes_the_validator_and_bad_links_fail(tmp_path):
    obj = build(["Place0 is a town in Liberia. " * 6, "Place1 is a lake in Liberia. " * 6])
    root: Path = tmp_path / "p"
    for rel, data in obj.files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data if isinstance(data, bytes) else data.read_bytes())
    manifest = json.loads((root / "manifest.json").read_text())
    for it in manifest["items"]:
        it["subject"] = "geography"
    (root / "manifest.json").write_text(json.dumps(manifest))
    write_sample_questions(root)
    qs = json.loads((root / "sample-questions.json").read_text())
    assert qs and validate(load_pack(root)).error_codes() <= {"META_HASH_MISMATCH"}
    qs[0]["passage"] = "wp:Nope#999"
    (root / "sample-questions.json").write_text(json.dumps(qs))
    assert "SAMPLE_QUESTION_BAD_PASSAGE" in validate(load_pack(root)).error_codes()
