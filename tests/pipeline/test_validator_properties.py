"""Property-based tests for the pack validator.

Spec: .kiro/specs/content-pipeline/requirements.md R6 (validation), R9 to R11; tasks.md 2.2.
Property: validate() fails exactly when a required field is missing, a license is not allowed,
offsets are wrong, a file or passage is orphaned, a forbidden term appears, or the hash is stale.
"""

from __future__ import annotations

import copy

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.validate import DEFAULT_ALLOWED_LICENSES, validate

from .packfactory import build, make_item, split_passages

# Letters and spaces only, so generated text can never contain the forbidden term by accident.
ARTICLE = st.text(alphabet="abcdfghijklmnopqrstuvwxyz ", min_size=60, max_size=400).map(lambda s: s.strip() + " end").filter(
    lambda s: "encarta" not in s.lower()
)
TEXTS = st.lists(ARTICLE, min_size=1, max_size=4)
REQUIRED = ["id", "type", "title", "source_url", "revision", "license", "attribution", "retrieved_at", "modifications"]


@settings(max_examples=60, deadline=None)
@given(TEXTS)
def test_valid_pack_passes(texts):
    report = validate(build(texts))
    assert report.ok, report.format()


@settings(max_examples=60, deadline=None)
@given(TEXTS, st.data())
def test_missing_required_field_fails(texts, data):
    items = [make_item(i) for i in range(len(texts))]
    victim = data.draw(st.integers(0, len(items) - 1))
    field = data.draw(st.sampled_from(REQUIRED))
    del items[victim][field]
    pack = build(texts, manifest_items=items)
    report = validate(pack)
    if field == "id":
        assert not report.ok
    else:
        assert "ITEM_FIELD_MISSING" in report.error_codes()


@settings(max_examples=60, deadline=None)
@given(TEXTS, st.text(alphabet="ABCXYZ-0123456789.", min_size=3, max_size=12).filter(lambda s: s not in DEFAULT_ALLOWED_LICENSES))
def test_disallowed_license_fails(texts, lic):
    items = [make_item(i, license=lic) for i in range(len(texts))]
    report = validate(build(texts, manifest_items=items))
    assert "LICENSE_NOT_ALLOWED" in report.error_codes()


@settings(max_examples=60, deadline=None)
@given(TEXTS, st.data())
def test_shifted_offsets_fail(texts, data):
    pack = build(texts)
    passages = copy.deepcopy(pack.passages)
    idx = data.draw(st.integers(0, len(passages) - 1))
    shift = data.draw(st.integers(1, 5))
    passages[idx]["start"] += shift
    passages[idx]["end"] += shift
    report = validate(build(texts, passages=passages))
    # Ground truth: the passage is valid exactly when its stored text equals the article slice.
    art = texts[int(passages[idx]["article"].removeprefix("wp:Article"))]
    p = passages[idx]
    still_valid = 0 <= p["start"] < p["end"] <= len(art) and art[p["start"] : p["end"]] == p["text"]
    if still_valid:
        assert report.ok, report.format()
    else:
        assert report.error_codes() & {"PASSAGE_TEXT_MISMATCH", "PASSAGE_OFFSETS_INVALID"}


@settings(max_examples=40, deadline=None)
@given(TEXTS)
def test_orphan_passage_fails(texts):
    passages = [p for i, t in enumerate(texts) for p in split_passages(f"wp:Article{i}", t)]
    passages.append({"id": "wp:Ghost#000", "article": "wp:Ghost", "text": "x", "start": 0, "end": 1, "heading_path": [], "words": 1})
    assert "PASSAGE_ORPHAN" in validate(build(texts, passages=passages)).error_codes()


@settings(max_examples=40, deadline=None)
@given(TEXTS, st.sampled_from(["Encarta", "ENCARTA", "encarta", "eNcArTa"]), st.data())
def test_forbidden_term_fails_in_any_case(texts, word, data):
    i = data.draw(st.integers(0, len(texts) - 1))
    texts = list(texts)
    texts[i] = texts[i] + " " + word
    assert "FORBIDDEN_TERM" in validate(build(texts)).error_codes()


@settings(max_examples=40, deadline=None)
@given(TEXTS)
def test_extra_file_and_missing_file(texts):
    extra = validate(build(texts, extra_files={"stray.bin": b"abc"}))
    assert "FILE_NOT_IN_MANIFEST" in extra.error_codes()
    missing = validate(build(texts, drop_files=("articles/a0.txt",)))
    assert "MANIFEST_FILE_MISSING" in missing.error_codes()


@settings(max_examples=40, deadline=None)
@given(TEXTS)
def test_stale_hash_fails(texts):
    assert "META_HASH_MISMATCH" in validate(build(texts, tamper_hash=True)).error_codes()
    # Changing a file after hashing also breaks the hash.
    pack = build(texts)
    pack.files["articles/a0.txt"] = pack.files["articles/a0.txt"] + b" changed"
    assert "META_HASH_MISMATCH" in validate(pack).error_codes()


@settings(max_examples=40, deadline=None)
@given(TEXTS)
def test_duplicate_ids_fail(texts):
    items = [make_item(i) for i in range(len(texts))] + [make_item(0)]
    assert "ITEM_DUPLICATE_ID" in validate(build(texts, manifest_items=items)).error_codes()


@settings(max_examples=40, deadline=None)
@given(st.lists(st.integers(0, 3), min_size=1, max_size=8), st.integers(0, 3))
def test_quiz_checks(opt_indexes, answer):
    text = "Liberia declared independence in 1847 and Monrovia is its capital city. " * 3
    texts = [text]
    pid = "wp:Article0#000"
    good = {
        "id": "q1", "subject": "history", "topic": "t", "difficulty": "easy", "type": "when",
        "stem": "When did Liberia declare independence?", "options": ["1822", "1847", "1857", "1878"], "answer": 1,
        "explanation": "e", "passage": pid, "generation": "hand", "reviewed": True,
    }
    assert validate(build(texts, quiz_bank=[good])).ok

    bad = copy.deepcopy(good)
    bad["reviewed"] = False
    assert "QUIZ_UNREVIEWED" in validate(build(texts, quiz_bank=[bad])).error_codes()

    bad = copy.deepcopy(good)
    bad["options"] = ["1847", "1847", "1857", "1878"]
    assert "QUIZ_BAD_OPTIONS" in validate(build(texts, quiz_bank=[bad])).error_codes()

    bad = copy.deepcopy(good)
    bad["passage"] = "wp:Missing#001"
    assert "QUIZ_BAD_PASSAGE" in validate(build(texts, quiz_bank=[bad])).error_codes()

    bad = copy.deepcopy(good)
    bad["options"], bad["answer"] = ["1822", "1999", "1857", "1878"], 1
    assert "QUIZ_ANSWER_NOT_IN_PASSAGE" in validate(build(texts, quiz_bank=[bad])).error_codes()

    bad = copy.deepcopy(good)
    bad["stem"] = "Liberia declared independence in 1847, when exactly?"
    assert "QUIZ_ANSWER_LEAK" in validate(build(texts, quiz_bank=[bad])).error_codes()
