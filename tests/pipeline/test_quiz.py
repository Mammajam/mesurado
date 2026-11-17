"""Tests for the quiz stage (spec: content-pipeline R11; tasks 6c.1, 6c.2)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.stages.quiz import (
    BLANK, build_bank, make_candidates, promote, stand_alone, write_candidates, write_quiz_bank,
)
from pipeline.validate import load_pack, validate
from tests.pipeline.packfactory import build


def passage(aid: str, n: int, text: str, heading=None) -> dict:
    return {"id": f"{aid}#{n:03d}", "article": aid, "heading_path": heading or [], "text": text, "start": 0, "end": len(text), "words": len(text.split())}


def data(n: int = 12):
    items, passages = [], []
    for i in range(n):
        aid = f"wp:Town{i}"
        items.append({"id": aid, "type": "article", "title": f"Town{i}", "subject": "geography", "coordinates": {"lat": 6.0 + i / 10, "lon": -10.0}})
        passages.append(passage(aid, 0, f"Town{i} is a coastal settlement in Liberia. The harbour at Town{i} was opened in {1900 + 3 * i} by local traders. "
                                         f"Farmers near Town{(i + 1) % n} grow cassava and rice for the weekly market."))
    return passages, items


def test_candidates_are_deterministic_and_have_four_distinct_options():
    passages, items = data()
    a = make_candidates(passages, items)
    assert a == make_candidates(passages, items) and a
    for c in a:
        assert len(c["options"]) == 4 and len({o.casefold() for o in c["options"]}) == 4
        assert c["options"][c["answer"]] and c["status"] == "pending" and c["generation"] == "rule" and "reviewed" not in c
        assert BLANK in c["stem"]


def test_every_candidate_satisfies_the_validator_rules_once_reviewed(tmp_path):
    passages, items = data()
    cands = make_candidates(passages, items)
    bank = build_bank([{**{k: v for k, v in c.items() if k != "status"}, "reviewed": True} for c in cands])
    texts = {p["id"]: p["text"] for p in passages}
    for q in bank["questions"]:
        correct = q["options"][q["answer"]]
        assert correct in texts[q["passage"]]  # answer found in passage
        assert correct not in q["stem"].replace(BLANK, "")  # blanked, no leak
        assert not any(o in q["stem"] for i, o in enumerate(q["options"]) if i != q["answer"])


def test_distractors_for_years_are_not_years_of_the_same_passage_and_titles_are_same_kind():
    passages, items = data()
    for c in make_candidates(passages, items):
        correct = c["options"][c["answer"]]
        text = next(p["text"] for p in passages if p["id"] == c["passage"])
        assert not any(o in text for i, o in enumerate(c["options"]) if i != c["answer"])
        if c["type"] == "cloze-title":
            assert all(o.startswith("Town") for o in c["options"]), correct  # all places, never a person or a county mixed in


def test_stand_alone_rejects_dangling_pronouns_numbers_and_parentheses():
    ok = "The harbour at Town3 was opened by local traders after a long dispute with the council."
    assert stand_alone(ok)
    assert not stand_alone("It was opened by local traders after a long dispute with the council of elders.")
    assert not stand_alone("The harbour (also called the port) was opened by local traders after a long dispute.")
    assert not stand_alone("Short sentence.")


def test_candidates_file_merge_never_overwrites_reviewer_work(tmp_path):
    passages, items = data()
    path = tmp_path / "candidates.yaml"
    cands = make_candidates(passages, items)
    added, kept = write_candidates(cands, path)
    assert (added, kept) == (len(cands), 0)
    doc = yaml.safe_load(path.read_text())
    doc["candidates"][0]["status"] = "accepted"
    doc["candidates"][0]["stem"] = "Reviewer's own wording: " + BLANK
    doc["candidates"][1]["status"] = "rejected"
    path.write_text(yaml.safe_dump(doc))
    added, kept = write_candidates(cands, path)  # regenerate
    again = yaml.safe_load(path.read_text())["candidates"]
    assert (added, kept) == (0, len(cands))
    assert again[0]["stem"].startswith("Reviewer's own wording") and again[0]["status"] == "accepted" and again[1]["status"] == "rejected"


def test_promote_moves_only_accepted_candidates_and_marks_them_reviewed(tmp_path):
    passages, items = data()
    cpath, rpath = tmp_path / "c.yaml", tmp_path / "r.yaml"
    write_candidates(make_candidates(passages, items), cpath)
    assert promote(cpath, rpath, "Expert") == 0 and not rpath.exists()  # nothing accepted, nothing promoted
    doc = yaml.safe_load(cpath.read_text())
    for c in doc["candidates"][:3]:
        c["status"] = "accepted"
    cpath.write_text(yaml.safe_dump(doc))
    assert promote(cpath, rpath, "Expert", today="2026-12-01") == 3
    reviewed = yaml.safe_load(rpath.read_text())["questions"]
    assert len(reviewed) == 3 and all(q["reviewed"] is True and q["reviewer"] == "Expert" and "status" not in q for q in reviewed)
    assert [c["status"] for c in yaml.safe_load(cpath.read_text())["candidates"][:3]] == ["promoted"] * 3
    assert promote(cpath, rpath, "Expert") == 0  # idempotent


def test_bank_leaves_out_reviewer_details_and_is_only_written_when_there_are_questions(tmp_path):
    q = {"id": "q-1", "subject": "geography", "topic": "t", "difficulty": "easy", "type": "cloze-year", "stem": "s " + BLANK,
         "options": ["a", "b", "c", "d"], "answer": 0, "explanation": "e", "explanationType": "copied", "passage": "wp:Town0#000",
         "generation": "rule", "reviewed": True, "reviewer": "Expert", "reviewed_on": "2026-12-01"}
    assert set(build_bank([q])["questions"][0]) == {k for k in q if k not in ("reviewer", "reviewed_on")}
    pack = tmp_path / "pack"
    pack.mkdir()
    empty = tmp_path / "empty.yaml"
    assert write_quiz_bank(pack, empty) == 0 and not (pack / "quiz-bank.json").exists()
    full = tmp_path / "full.yaml"
    full.write_text(yaml.safe_dump({"questions": [q]}))
    assert write_quiz_bank(pack, full) == 1 and json.loads((pack / "quiz-bank.json").read_text())["format"] == "mesurado-quiz-1"


def test_validator_accepts_a_reviewed_bank_and_rejects_unreviewed_questions(tmp_path):
    texts = ["Town0 is a coastal settlement in Liberia. The harbour was opened in 1903 by local traders and it grew fast."]
    obj = build(texts)
    root: Path = tmp_path / "p"
    for rel, d in obj.files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(d if isinstance(d, bytes) else d.read_bytes())
    pid = json.loads((root / "passages.jsonl").read_text().splitlines()[0])["id"]
    ptext = json.loads((root / "passages.jsonl").read_text().splitlines()[0])["text"]
    answer = next(w for w in ["Town0", "Liberia", "harbour"] if w in ptext)
    q = {"id": "q-1", "subject": "geography", "topic": "t", "difficulty": "easy", "type": "cloze-title", "stem": "Fill in the blank: ____ is a place.",
         "options": [answer, "Xyz", "Uvw", "Rst"], "answer": 0, "explanation": "e", "explanationType": "copied", "passage": pid,
         "generation": "rule", "reviewed": True}
    (root / "quiz-bank.json").write_text(json.dumps({"questions": [q]}))
    assert validate(load_pack(root)).error_codes() - {"META_HASH_MISMATCH"} == set()
    q["reviewed"] = False
    (root / "quiz-bank.json").write_text(json.dumps({"questions": [q]}))
    assert "QUIZ_UNREVIEWED" in validate(load_pack(root)).error_codes()


@settings(max_examples=25, deadline=None)
@given(st.integers(5, 40))
def test_selection_caps_hold_for_any_pack_size(n):
    passages, items = data(n)
    cands = make_candidates(passages, items, per_subject=10)
    assert len(cands) <= 10 and len({c["id"] for c in cands}) == len(cands)
    per_article: dict[str, int] = {}
    for c in cands:
        a = c["passage"].split("#")[0]
        per_article[a] = per_article.get(a, 0) + 1
    assert all(v <= 3 for v in per_article.values())
