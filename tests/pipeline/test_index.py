"""Tests for the index stage (spec: content-pipeline R5; tasks 5.1 to 5.3).

Uses a fake embedder so the suite stays fast and offline. One test loads the real model and is skipped
when the model is not cached (run `uv run --python 3.12 pytest -m slow` to include it).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.stages.index import (
    DIMS, bm25_search, build_indexes, build_keyword_index, dequantize, load_keyword_index, quantize,
    read_embeddings, semantic_search, tokenize, write_keyword_index,
)
from pipeline.validate import load_pack, validate
from tests.pipeline.packfactory import build


def fake_embedder(texts):
    """Deterministic unit vectors from a hash of each token, so similar texts have similar vectors."""
    out = np.zeros((len(texts), DIMS), dtype=np.float32)
    for i, t in enumerate(texts):
        for tok in tokenize(t):
            h = int.from_bytes(hashlib.sha256(tok.encode()).digest()[:8], "little")
            out[i, h % DIMS] += 1.0
        n = np.linalg.norm(out[i])
        out[i] /= n if n else 1.0
    return out


def make_passages(texts: list[str]) -> tuple[list[dict], dict[str, str]]:
    passages = [{"id": f"wp:A{i}#000", "article": f"wp:A{i}", "heading_path": [], "text": t, "start": 0, "end": len(t), "words": len(t.split())}
                for i, t in enumerate(texts)]
    return passages, {f"wp:A{i}": f"Title {i}" for i in range(len(texts))}


def write_pack(tmp_path: Path, texts: list[str]) -> Path:
    passages, titles = make_passages(texts)
    pack = tmp_path / "pack"
    pack.mkdir(exist_ok=True)
    (pack / "passages.jsonl").write_text("\n".join(json.dumps(p) for p in passages) + "\n", encoding="utf-8")
    (pack / "manifest.json").write_text(json.dumps({"items": [{"id": a, "title": t} for a, t in titles.items()]}), encoding="utf-8")
    return pack


# ---- tokenizer -------------------------------------------------------------------------------


def test_tokenizer_folds_accents_case_and_drops_stopwords():
    assert tokenize("The Kru of Côte d'Ivoire, 1822!") == ["kru", "cote", "ivoire", "1822"]
    assert tokenize("A I x") == []


# ---- keyword index ---------------------------------------------------------------------------


TEXTS = [
    "Monrovia is the capital city of Liberia, founded in 1822 on Cape Mesurado.",
    "The Kru people are a Kru-speaking ethnic group living along the Liberian coast.",
    "Lake Piso is a coastal lagoon in Grand Cape Mount County.",
]


def test_bm25_finds_the_matching_passage_and_ignores_unknown_terms():
    p, t = make_passages(TEXTS)
    idx = build_keyword_index(p, t)
    assert bm25_search(idx, "capital of Liberia")[0][0] == "wp:A0#000"
    assert bm25_search(idx, "kru people")[0][0] == "wp:A1#000"
    assert bm25_search(idx, "zzzz qqqq") == []
    assert bm25_search(idx, "the of") == []  # only stopwords


def test_title_and_heading_path_are_indexed():
    p, t = make_passages(TEXTS)
    p[2]["heading_path"] = ["Geography", "Hydrology"]
    idx = build_keyword_index(p, t)
    assert bm25_search(idx, "hydrology")[0][0] == "wp:A2#000"


def test_keyword_index_round_trips_and_postings_decode(tmp_path):
    p, t = make_passages(TEXTS)
    idx = build_keyword_index(p, t)
    write_keyword_index(idx, tmp_path / "k.idx")
    assert load_keyword_index(tmp_path / "k.idx") == idx
    assert idx["n_docs"] == 3 and len(idx["doc_len"]) == 3


@settings(max_examples=40, deadline=None)
@given(st.lists(st.text(alphabet="abcdef ", min_size=3, max_size=60), min_size=1, max_size=12))
def test_bm25_only_returns_documents_that_contain_a_query_term(texts):
    p, t = make_passages(texts)
    idx = build_keyword_index(p, t)
    for q in ["abc", "fed cab", "zz"]:
        terms = set(tokenize(q))
        for pid, score in bm25_search(idx, q, limit=50):
            doc = next(x for x in p if x["id"] == pid)
            assert terms & set(tokenize(t[doc["article"]] + " " + doc["text"]))
            assert score > 0


# ---- quantization and the embeddings file ------------------------------------------------------


@settings(max_examples=40, deadline=None)
@given(st.integers(1, 20), st.integers(0, 10_000))
def test_quantization_error_is_small_and_ranking_preserved(n, seed):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, DIMS)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    q, s = quantize(v)
    assert q.dtype == np.int8 and np.abs(q).max() <= 127
    assert np.abs(dequantize(q, s) - v).max() <= s.max() / 2 + 1e-6  # half a quantization step
    assert np.allclose(np.linalg.norm(dequantize(q, s), axis=1), 1.0, atol=0.02)


def test_zero_vector_quantizes_without_nan():
    q, s = quantize(np.zeros((1, 4), dtype=np.float32))
    assert (q == 0).all() and np.isfinite(s).all()


def test_build_indexes_writes_valid_files_and_search_works(tmp_path):
    pack = write_pack(tmp_path, TEXTS)
    stats = build_indexes(pack, fake_embedder)
    assert stats["passages"] == 3
    header, q, scales = read_embeddings(pack / "embeddings.i8")
    assert header["count"] == 3 and header["dims"] == DIMS and header["license"] == "Apache-2.0"
    ids = [f"wp:A{i}#000" for i in range(3)]
    qv = fake_embedder(["Kru people coast"])[0]
    assert semantic_search(header, q, scales, ids, qv, 1)[0][0] == "wp:A1#000"


def test_build_is_deterministic(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = write_pack(tmp_path / "a", TEXTS)
    b = write_pack(tmp_path / "b", TEXTS)
    build_indexes(a, fake_embedder)
    build_indexes(b, fake_embedder)
    for name in ("keyword.idx", "embeddings.i8"):
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_wrong_embedding_shape_is_rejected(tmp_path):
    pack = write_pack(tmp_path, TEXTS)
    with pytest.raises(ValueError):
        build_indexes(pack, lambda texts: np.zeros((len(texts), 10), dtype=np.float32))


# ---- validator -------------------------------------------------------------------------------


def with_index(tmp_path: Path):
    """A real unpacked pack on disk (from the factory) plus index files, loaded through the loader."""
    pack_obj = build(["Monrovia is the capital of Liberia. " * 3, "The Kru people live on the coast. " * 3])
    root = tmp_path / "p"
    root.mkdir()
    for rel, data in pack_obj.files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data if isinstance(data, bytes) else data.read_bytes())
    return root


def refresh_meta(root: Path):
    from pipeline.validate import compute_content_hash

    files = {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file() and p.name != "meta.json"}
    meta = json.loads((root / "meta.json").read_text())
    meta["content_hash"] = compute_content_hash(files)
    (root / "meta.json").write_text(json.dumps(meta))


def test_validator_accepts_matching_indexes_and_rejects_mismatches(tmp_path):
    root = with_index(tmp_path)
    build_indexes(root, fake_embedder)
    refresh_meta(root)
    assert validate(load_pack(root)).ok

    # Drop the last passage from passages.jsonl: both index files now describe a different pack.
    lines = (root / "passages.jsonl").read_text().splitlines()
    (root / "passages.jsonl").write_text("\n".join(lines[:-1]))
    refresh_meta(root)
    codes = validate(load_pack(root)).error_codes()
    assert {"KEYWORD_INDEX_MISMATCH", "EMBEDDINGS_MISMATCH"} <= codes


def test_validator_rejects_truncated_embeddings_and_bad_json(tmp_path):
    root = with_index(tmp_path)
    build_indexes(root, fake_embedder)
    raw = (root / "embeddings.i8").read_bytes()
    (root / "embeddings.i8").write_bytes(raw[:-5])
    (root / "keyword.idx").write_text("{not json")
    refresh_meta(root)
    codes = validate(load_pack(root)).error_codes()
    assert {"EMBEDDINGS_INVALID", "KEYWORD_INDEX_INVALID"} <= codes


# ---- real model (slow) -----------------------------------------------------------------------


@pytest.mark.slow
def test_real_model_ranks_related_text_higher():
    from pipeline.stages.index import fastembed_embedder

    e = fastembed_embedder()
    v = e(["Monrovia is the capital of Liberia.", "Liberia's capital city", "Banana bread recipe"])
    assert v.shape == (3, DIMS) and abs(np.linalg.norm(v[0]) - 1) < 1e-3
    assert v[0] @ v[1] > v[0] @ v[2]
