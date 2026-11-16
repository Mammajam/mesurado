"""Build small valid packs in memory for validator tests."""

from __future__ import annotations

import copy
import json
from typing import Any

from pipeline.validate import Pack, compute_content_hash

GOOD_LICENSE = "CC-BY-SA-4.0"


def make_item(n: int, **over: Any) -> dict[str, Any]:
    item = {
        "id": f"wp:Article{n}",
        "type": "article",
        "title": f"Article {n}",
        "source_url": f"https://en.wikipedia.org/wiki/Article_{n}",
        "revision": str(1000 + n),
        "license": GOOD_LICENSE,
        "attribution": "Wikipedia contributors",
        "retrieved_at": "2026-11-20",
        "modifications": ["cleaned", "split into passages"],
        "text_file": f"articles/a{n}.txt",
    }
    item.update(over)
    return item


def split_passages(aid: str, text: str, size: int = 40) -> list[dict[str, Any]]:
    out = []
    for k, start in enumerate(range(0, len(text), size)):
        end = min(start + size, len(text))
        out.append({"id": f"{aid}#{k:03d}", "article": aid, "heading_path": [], "text": text[start:end], "start": start, "end": end, "words": 1})
    return out


def build(
    texts: list[str],
    *,
    manifest_items: list[dict[str, Any]] | None = None,
    passages: list[dict[str, Any]] | None = None,
    extra_files: dict[str, bytes] | None = None,
    sample_questions: Any = None,
    timeline: Any = None,
    quiz_bank: Any = None,
    drop_files: tuple[str, ...] = (),
    meta_extra: dict[str, Any] | None = None,
    tamper_hash: bool = False,
) -> Pack:
    items = manifest_items if manifest_items is not None else [make_item(i) for i in range(len(texts))]
    pass_ = passages if passages is not None else [p for i, t in enumerate(texts) for p in split_passages(f"wp:Article{i}", t)]
    files: dict[str, bytes] = {}
    articles: dict[str, str] = {}
    for i, t in enumerate(texts):
        files[f"articles/a{i}.txt"] = t.encode("utf-8")
        articles[f"wp:Article{i}"] = t
    files["manifest.json"] = json.dumps({"items": items}).encode()
    files["passages.jsonl"] = "\n".join(json.dumps(p) for p in pass_).encode()
    if sample_questions is not None:
        files["sample-questions.json"] = json.dumps(sample_questions).encode()
    if timeline is not None:
        files["timeline.json"] = json.dumps(timeline).encode()
    if quiz_bank is not None:
        files["quiz-bank.json"] = json.dumps(quiz_bank).encode()
    for k, v in (extra_files or {}).items():
        files[k] = v
    for k in drop_files:
        files.pop(k, None)
    h = compute_content_hash(files)
    if tamper_hash:
        h = "0" * 64
    meta = {"version": "test", "content_hash": h, **(meta_extra or {})}
    files["meta.json"] = json.dumps(meta).encode()
    return Pack(
        manifest={"items": copy.deepcopy(items)},
        passages=copy.deepcopy(pass_),
        articles=articles,
        meta=meta,
        sample_questions=sample_questions,
        timeline=timeline,
        quiz_bank=quiz_bank,
        files=files,
    )
