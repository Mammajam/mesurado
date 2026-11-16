"""Load an unpacked pack directory into a Pack (spec: content-pipeline design, "Data formats")."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import Issue, Pack


def _read_json(path: Path, rel: str, pack: Pack) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        pack.load_errors.append(Issue("JSON_INVALID", f"{rel} is not valid JSON: {exc}", rel))
        return None


def load_pack(root: str | Path) -> Pack:
    """Read a pack directory.

    Layout: manifest.json, passages.jsonl, meta.json, articles/*.txt (UTF-8, referenced by
    manifest item field `text_file`), plus optional sample-questions.json, timeline.json,
    quiz-bank.json and any other files listed in the manifest.
    """
    root = Path(root)
    pack = Pack()
    if not root.is_dir():
        pack.load_errors.append(Issue("PACK_NOT_FOUND", f"{root} is not a directory", str(root)))
        return pack

    for p in sorted(root.rglob("*")):
        if p.is_file():
            pack.files[p.relative_to(root).as_posix()] = p

    pack.manifest = _read_json(root / "manifest.json", "manifest.json", pack)
    pack.meta = _read_json(root / "meta.json", "meta.json", pack)
    pack.sample_questions = _read_json(root / "sample-questions.json", "sample-questions.json", pack)
    pack.timeline = _read_json(root / "timeline.json", "timeline.json", pack)
    pack.quiz_bank = _read_json(root / "quiz-bank.json", "quiz-bank.json", pack)

    pj = root / "passages.jsonl"
    if pj.is_file():
        passages: list[dict[str, Any]] = []
        try:
            for n, line in enumerate(pj.read_text(encoding="utf-8").splitlines(), start=1):
                if line.strip():
                    passages.append(json.loads(line))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            pack.load_errors.append(Issue("JSON_INVALID", f"passages.jsonl line {n}: {exc}", "passages.jsonl"))
        pack.passages = passages

    items = pack.manifest.get("items") if isinstance(pack.manifest, dict) else None
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("type") == "article" and item.get("text_file"):
                f = root / str(item["text_file"])
                if f.is_file():
                    try:
                        pack.articles[str(item.get("id"))] = f.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        pack.load_errors.append(
                            Issue("ARTICLE_TEXT_INVALID", f"{item['text_file']} is not UTF-8", str(item.get("id")))
                        )
    return pack
