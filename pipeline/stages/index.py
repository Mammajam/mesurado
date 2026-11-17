"""Index stage: keyword index and int8 embeddings for a pack (spec: content-pipeline R5; search design).

Files written into the unpacked pack directory:
  keyword.idx    JSON, format "mesurado-keyword-1": tokenizer config, doc ids, doc lengths, postings
  embeddings.i8  binary: b"MSE1" + u32 header length + JSON header + float32 scales[count] + int8[count*dims]

Both are deterministic: the same passages (and the same model) give byte-identical files.
The client re-implements the tokenizer and BM25 in JavaScript; `tokenize` and `bm25_search` here are
the reference the client is tested against.
"""

from __future__ import annotations

import json
import math
import re
import struct
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

KEYWORD_FORMAT = "mesurado-keyword-1"
EMBED_MAGIC = b"MSE1"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_LICENSE = "Apache-2.0"
DIMS = 384
MIN_TOKEN = 2
STOPWORDS = frozenset(
    "a an and are as at be been but by for from had has have he her his i in is it its of on or she that the their "
    "them they this to was were which who will with you your".split()
)
_SPLIT = re.compile(r"[^0-9a-z]+")
BM25_K1 = 1.2
BM25_B = 0.75


def tokenize(text: str) -> list[str]:
    """Lower-case, strip accents (NFKD), split on non-alphanumerics, drop short tokens and stopwords."""
    folded = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    return [t for t in _SPLIT.split(folded) if len(t) >= MIN_TOKEN and t not in STOPWORDS]


def index_text(passage: dict, title: str) -> str:
    """The text a passage is indexed under: article title, heading path, then the passage itself."""
    return " ".join([title, *passage.get("heading_path", []), passage["text"]])


# ---- keyword index ---------------------------------------------------------------------------


def build_keyword_index(passages: Sequence[dict], titles: dict[str, str]) -> dict:
    doc_ids = [p["id"] for p in passages]
    doc_len: list[int] = []
    postings: dict[str, list[tuple[int, int]]] = {}
    for i, p in enumerate(passages):
        toks = tokenize(index_text(p, titles.get(p["article"], "")))
        doc_len.append(len(toks))
        for term, tf in Counter(toks).items():
            postings.setdefault(term, []).append((i, tf))
    encoded: dict[str, list[int]] = {}
    for term in sorted(postings):
        flat: list[int] = []
        prev = 0
        for doc, tf in postings[term]:  # docs ascend, so deltas are small and non-negative
            flat += [doc - prev, tf]
            prev = doc
        encoded[term] = flat
    return {
        "format": KEYWORD_FORMAT,
        "tokenizer": {"fold": "NFKD-strip-marks", "lower": True, "split": "[^0-9a-z]+", "min_length": MIN_TOKEN,
                      "stopwords": sorted(STOPWORDS)},
        "bm25": {"k1": BM25_K1, "b": BM25_B},
        "n_docs": len(doc_ids),
        "avgdl": round(sum(doc_len) / max(1, len(doc_len)), 4),
        "doc_ids": doc_ids,
        "doc_len": doc_len,
        "postings": encoded,
    }


def write_keyword_index(index: dict, path: Path) -> None:
    path.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def load_keyword_index(path: Path) -> dict:
    index = json.loads(path.read_text(encoding="utf-8"))
    if index.get("format") != KEYWORD_FORMAT:
        raise ValueError(f"unknown keyword index format: {index.get('format')!r}")
    return index


def bm25_search(index: dict, query: str, limit: int = 10) -> list[tuple[str, float]]:
    """Reference BM25 over a loaded keyword index. Returns (passage id, score), best first, ties by id."""
    n, avgdl = index["n_docs"], index["avgdl"] or 1.0
    k1, b = index["bm25"]["k1"], index["bm25"]["b"]
    scores: dict[int, float] = {}
    for term in dict.fromkeys(tokenize(query)):
        flat = index["postings"].get(term)
        if not flat:
            continue
        df = len(flat) // 2
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        doc = 0
        for k in range(0, len(flat), 2):
            doc += flat[k]
            tf = flat[k + 1]
            norm = tf + k1 * (1 - b + b * index["doc_len"][doc] / avgdl)
            scores[doc] = scores.get(doc, 0.0) + idf * tf * (k1 + 1) / norm
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], index["doc_ids"][kv[0]]))
    return [(index["doc_ids"][d], s) for d, s in ranked[:limit]]


# ---- embeddings ------------------------------------------------------------------------------

Embedder = Callable[[Sequence[str]], np.ndarray]


def quantize(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-vector symmetric int8 quantization. Returns (int8 [n, d], float32 scales [n])."""
    vectors = np.asarray(vectors, dtype=np.float32)
    peak = np.abs(vectors).max(axis=1)
    scales = np.where(peak > 0, peak / 127.0, 1.0).astype(np.float32)
    q = np.clip(np.rint(vectors / scales[:, None]), -127, 127).astype(np.int8)
    return q, scales


def dequantize(q: np.ndarray, scales: np.ndarray) -> np.ndarray:
    return q.astype(np.float32) * scales[:, None]


def write_embeddings(q: np.ndarray, scales: np.ndarray, doc_ids: Sequence[str], path: Path, model: str = MODEL_NAME) -> None:
    header = json.dumps({
        "format": "mesurado-embeddings-1", "model": model, "license": MODEL_LICENSE, "dims": int(q.shape[1]),
        "count": int(q.shape[0]), "quantization": "int8-per-vector-symmetric", "normalized": True,
        "first_id": doc_ids[0] if doc_ids else "", "last_id": doc_ids[-1] if doc_ids else "",
    }, sort_keys=True).encode("utf-8")
    with path.open("wb") as f:
        f.write(EMBED_MAGIC + struct.pack("<I", len(header)) + header)
        f.write(scales.astype("<f4").tobytes())
        f.write(q.astype(np.int8).tobytes())


def read_embeddings(path: Path) -> tuple[dict, np.ndarray, np.ndarray]:
    raw = path.read_bytes()
    if raw[:4] != EMBED_MAGIC:
        raise ValueError("not an embeddings file (bad magic)")
    (hlen,) = struct.unpack("<I", raw[4:8])
    header = json.loads(raw[8:8 + hlen])
    n, d = header["count"], header["dims"]
    off = 8 + hlen
    if len(raw) != off + 4 * n + n * d:
        raise ValueError(f"embeddings file size {len(raw)} does not match header (count={n}, dims={d})")
    scales = np.frombuffer(raw, dtype="<f4", count=n, offset=off).astype(np.float32)
    q = np.frombuffer(raw, dtype=np.int8, count=n * d, offset=off + 4 * n).reshape(n, d)
    return header, q, scales


def fastembed_embedder(model: str = MODEL_NAME) -> Embedder:
    from fastembed import TextEmbedding

    m = TextEmbedding(model)

    def embed(texts: Sequence[str]) -> np.ndarray:
        return np.array(list(m.embed(list(texts), batch_size=32)), dtype=np.float32)

    return embed


def semantic_search(header: dict, q: np.ndarray, scales: np.ndarray, doc_ids: Sequence[str], query_vec: np.ndarray, limit: int = 10) -> list[tuple[str, float]]:
    sims = (q.astype(np.float32) @ query_vec.astype(np.float32)) * scales
    order = sorted(range(len(sims)), key=lambda i: (-float(sims[i]), doc_ids[i]))[:limit]
    return [(doc_ids[i], float(sims[i])) for i in order]


# ---- stage entry points ----------------------------------------------------------------------


def read_pack_passages(pack: Path) -> tuple[list[dict], dict[str, str]]:
    passages = [json.loads(line) for line in (pack / "passages.jsonl").read_text(encoding="utf-8").splitlines() if line]
    items = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))["items"]
    return passages, {i["id"]: i["title"] for i in items if i.get("type") == "article"}


def build_indexes(pack: Path, embedder: Embedder | None = None, log=lambda s: None) -> dict:
    """Write keyword.idx and embeddings.i8 into an unpacked pack directory. Returns size/count stats."""
    passages, titles = read_pack_passages(pack)
    kw = build_keyword_index(passages, titles)
    write_keyword_index(kw, pack / "keyword.idx")
    log(f"keyword index: {len(kw['postings'])} terms")
    embed = embedder or fastembed_embedder()
    texts = [index_text(p, titles.get(p["article"], "")) for p in passages]
    vectors = embed(texts)
    if vectors.shape != (len(passages), DIMS):
        raise ValueError(f"embedder returned shape {vectors.shape}, expected {(len(passages), DIMS)}")
    q, scales = quantize(vectors)
    write_embeddings(q, scales, [p["id"] for p in passages], pack / "embeddings.i8")
    return {
        "passages": len(passages), "terms": len(kw["postings"]),
        "keyword_bytes": (pack / "keyword.idx").stat().st_size, "embedding_bytes": (pack / "embeddings.i8").stat().st_size,
    }


def main(argv: list[str]) -> int:
    from pipeline.stages.assemble import OUT_DIR

    pack = Path(argv[0]) if argv else OUT_DIR / "dev"
    stats = build_indexes(pack, log=print)
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
